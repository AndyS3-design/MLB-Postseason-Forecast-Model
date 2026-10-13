"""Official MLB schedule parser and leakage-safe Elo utility for baseball model."""
from __future__ import annotations

from datetime import date, datetime, timezone
from itertools import groupby
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

import pandas as pd

from extended_eval import all_games, K, HOME_ELO, OFFSEASON
from ingest_mlb import MLB_TO_RETRO, API

TEAM_NAMES = {
    'ANA':'Los Angeles Angels', 'ARI':'Arizona Diamondbacks','ATL':'Atlanta Braves',
    'BAL':'Baltimore Orioles','BOS':'Boston Red Sox','CHA':'Chicago White Sox',
    'CHN':'Chicago Cubs','CIN':'Cincinnati Reds','CLE':'Cleveland Guardians',
    'COL':'Colorado Rockies','DET':'Detroit Tigers','HOU':'Houston Astros',
    'KCA':'Kansas City Royals','LAN':'Los Angeles Dodgers','MIA':'Miami Marlins',
    'MIL':'Milwaukee Brewers','MIN':'Minnesota Twins','NYA':'New York Yankees',
    'NYN':'New York Mets','OAK':'Athletics','PHI':'Philadelphia Phillies',
    'PIT':'Pittsburgh Pirates','SDN':'San Diego Padres','SEA':'Seattle Mariners',
    'SFN':'San Francisco Giants','SLN':'St. Louis Cardinals','TBA':'Tampa Bay Rays',
    'TEX':'Texas Rangers','TOR':'Toronto Blue Jays','WAS':'Washington Nationals',
}


def date_only(value):
    if isinstance(value, pd.Timestamp): return value.date()
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    return date.fromisoformat(str(value)[:10])


def historical_snapshot(games: list[dict], target_day: date):
    """Return history only; future and same-day outcomes MUST never enter."""
    d=date_only(target_day)
    filtered=[g.copy() for g in games if date_only(g['date']) < d]
    filtered.sort(key=lambda r:(date_only(r['date']),int(str(r.get('game_type','R'))!='R'),str(r.get('game_num',''))))
    return filtered


def elo_ratings(games: list[dict]):
    """Apply Elo updates only after all games on a date have been grouped."""
    ratings={}; previous_year=None
    for (year,day), grp in groupby(games, key=lambda g:(int(g['year']),date_only(g['date']))):
        today=list(grp)
        if year!=previous_year:
            if previous_year is not None:
                ratings={team:rating*OFFSEASON for team,rating in ratings.items()}
            previous_year=year
        deltas=defaultdict(float)
        for g in today:
            h=ratings.get(g['home'],0.0); a=ratings.get(g['away'],0.0)
            p=1/(1+10**((a-h-HOME_ELO)/400))
            actual=int(g['home_final']>g['away_final'])
            d=K*(actual-p)
            deltas[g['home']]+=d;deltas[g['away']]-=d
        for team,delta in deltas.items():ratings[team]=ratings.get(team,0.0)+delta
    return ratings, previous_year


def elo_probability(history: list[dict], target_day, home: str, away: str):
    if home==away: raise ValueError('Home and away teams must differ.')
    if home not in TEAM_NAMES or away not in TEAM_NAMES:
        raise ValueError('Unsupported MLB team code.')
    rating,last_year=elo_ratings(history)
    if last_year is None: raise ValueError('No historical games before this date.')
    # Offseason regression also applies when forecasting the next season's first game.
    target_year=date_only(target_day).year
    if target_year>last_year:
        for _ in range(target_year-last_year):
            rating={team:value*OFFSEASON for team,value in rating.items()}
    rh=rating.get(home,0.0);ra=rating.get(away,0.0)
    return 1/(1+10**((ra-rh-HOME_ELO)/400)),rh,ra


def parse_schedule(payload: dict, scheduled_day: date):
    """Extract real named matchups from MLB schedule response; no fabricated fixtures."""
    day=date_only(scheduled_day)
    out=[]
    for block in payload.get('dates',[]):
        for g in block.get('games',[]):
            if date_only(g.get('officialDate') or block.get('date'))!=day: continue
            teams=g.get('teams',{})
            try:
                h=teams['home'];a=teams['away']
                hc=MLB_TO_RETRO[int(h['team']['id'])]
                ac=MLB_TO_RETRO[int(a['team']['id'])]
            except (KeyError, ValueError, TypeError):continue
            if hc==ac:continue
            def pitcher(team):
                info=team.get('probablePitcher') or {}
                return info.get('fullName') or 'Not announced'
            def pitcher_id(team):
                info=team.get('probablePitcher') or {}
                return ('MLB-'+str(info['id'])) if info.get('id') else ''
            out.append({'id':str(g.get('gamePk','')),'date':day.isoformat(),
               'home':hc,'away':ac,
               'home_name':h['team'].get('name') or TEAM_NAMES[hc],
               'away_name':a['team'].get('name') or TEAM_NAMES[ac],
               'home_pitcher':pitcher(h),'away_pitcher':pitcher(a),
               'home_pitcher_id':pitcher_id(h),'away_pitcher_id':pitcher_id(a),
               'start_utc':g.get('gameDate'),'status':g.get('status',{}).get('detailedState','Unknown'),
               'game_type':g.get('gameType','')})
    return out


def fetch_schedule(scheduled_day: date, timeout=15):
    params={'sportId':1,'date':date_only(scheduled_day).isoformat(),
            'hydrate':'probablePitcher'}
    url=API+'?'+urlencode(params)
    req=Request(url,headers={'User-Agent':'MLB research forecast dashboard / 1.0'})
    with urlopen(req,timeout=timeout) as f:
        payload=json.load(f)
    return parse_schedule(payload,scheduled_day)
