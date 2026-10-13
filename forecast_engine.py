"""Pregame-only MLB probabilities using the existing research-kit models.

Elo is the validated winner baseline. The game-total run model is experimental.
All forecasts for a date D use only finalized games with game dates < D.
No probable-pitcher information is used in the probabilities.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from itertools import groupby
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import math

import numpy as np
import pandas as pd

from backtest import read_rows, make_features, train, preds, dispersion, extra_model, game_probs, FEATURE_NAMES
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


def build_run_fit(data_dir: Path):
    """Frozen 2023-24 regular-season fit; no 2025 or 2026 outcomes in the fit."""
    rows=read_rows(data_dir)
    frame=make_features(rows)
    feat=[c for c in FEATURE_NAMES if '_sp_' not in c]
    train23=frame[frame.year==2023]
    val24=frame[frame.year==2024]
    fit23=train(train23,feat)
    hm,aw=preds(fit23,val24,feat)
    ah=dispersion(hm,val24.home_reg)
    aa=dispersion(aw,val24.away_reg)
    tr=frame[frame.year.isin([2023,2024])]
    return (train(tr,feat),feat,ah,aa,extra_model(tr))


def _run_feature_row(history, day: date, home, away):
    """Append a sentinel game; its fake score is NEVER read during feature creation.

    make_features creates all features for a date before recording any results
    from that date. The sentinel exists only so we can request a feature row;
    we never use it for training or mark it as a result.
    """
    usable=[]
    for g in history:
        v=g.copy()
        # Archived 2025 postseason and some API games omit regulation linescores.
        # Use past known final scores as a noisy proxy, not as target-game data.
        for reg,final in [('home_reg','home_final'),('away_reg','away_final')]:
            if pd.isna(v.get(reg)):
                v[reg]=float(v[final])
        usable.append(v)
    sentinel={'year':day.year,'date':pd.Timestamp(day),'game_num':'PREDICTION_ONLY',
              'home':home,'away':away,'home_final':1,'away_final':0,
              'home_reg':1,'away_reg':0,'home_sp':'','away_sp':'',
              'game_type':'PREDICTION_ONLY','source':'none'}
    usable.append(sentinel)
    usable.sort(key=lambda g:(date_only(g['date']),str(g.get('game_num',''))))
    features=make_features(usable)
    return features[features.game_num=='PREDICTION_ONLY'].iloc[[-1]].copy()


def forecast(games: list[dict], day, home: str, away: str, run_fit=None):
    d=date_only(day)
    if d.year<2023 or d.year>2026:
        raise ValueError('The bundled project supports 2023–2026. Extend its importer for future seasons.')
    history=historical_snapshot(games,d)
    p,rh,ra=elo_probability(history,d,home,away)
    result={'home':home,'away':away,'date':d.isoformat(),
            'home_win_probability':float(p),'away_win_probability':float(1-p),
            'home_rating':float(rh),'away_rating':float(ra),
            'past_games_used':len(history),
            'last_completed_date':max((date_only(g['date']) for g in history),default=None),
            'games_in_target_season':sum(g['year']==d.year for g in history),
            'total_status':'Unavailable until run model is fitted',
            'pitcher_effect':'Not included in probability models'}
    if run_fit is not None:
        models,feature_names,alpha_h,alpha_a,extra=run_fit
        x=_run_feature_row(history,d,home,away)
        mh,ma=preds(models,x,feature_names)
        mu_h=float(mh[0]);mu_a=float(ma[0])
        p_run_home,p_under=game_probs(mu_h,mu_a,alpha_h,alpha_a,extra)
        result.update(home_runs_regulation=mu_h,away_runs_regulation=mu_a,
           combined_runs_regulation=mu_h+mu_a,
           under_6_5_probability=float(p_under),over_6_5_probability=float(1-p_under),
           home_win_run_model=float(p_run_home),
           total_status='Experimental: 2023–24-trained, weak totals holdout; no starting-pitcher adjustment')
    return result


def quote_analysis(win_probability: float, ask_cents: float, fee_cents: float):
    """One $1 YES contract; ask and fee from user, NOT live Kalshi quotes."""
    p=float(win_probability); ask=float(ask_cents); fee=float(fee_cents)
    if not(0<=p<=1): raise ValueError('Probability must be between 0 and 1')
    if not(0<ask<100): raise ValueError('YES ask must be between 0 and 100 cents')
    if not(0<=fee<100) or ask+fee>=100:
        raise ValueError('Ask plus fees must be less than $1 payout')
    cost=(ask+fee)/100
    return {'yes_probability':p,'break_even_probability':cost,'edge_pp':100*(p-cost),
            'expected_value_usd_per_contract':p-cost,
            'win_profit_usd':1-cost,'loss_usd':-cost,
            'maximum_payout_usd':1.0}


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
