"""Official MLB data refresh, with immutable pregame cutoffs and atomic writes.

No sportsbook/market data. Never import games with official dates >= today ET.
"""
from __future__ import annotations
import csv, json, warnings
from datetime import date,timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from ingest_mlb import schedule_from_response,COLUMNS,MLB_TO_RETRO

API='https://statsapi.mlb.com/api/v1/schedule'


def fetch_json(url,timeout=35):
    with urlopen(Request(url,headers={'User-Agent':'MLB Forecast Lab baseball-only educational study'}),timeout=timeout) as f:
        return json.load(f)


def chunks(start,end,days=38):
    cursor=start
    while cursor<end:
        later=min(end,cursor+timedelta(days=days))
        yield cursor,later-timedelta(days=1)
        cursor=later


def current_season_results(root:Path,as_of:date,fetcher=fetch_json):
    """Fetch completed results strictly before an ET calendar date.

    Do NOT silently delete any previously valid records when the API fails.
    """
    if as_of.year<2026:return 0
    incoming=[]
    years=range(2026,as_of.year+1)
    for year in years:
        start=date(year,3,1)
        if start>=as_of:continue
        for a,b in chunks(start, min(as_of,date(year+1,1,1))):
            q=urlencode({'sportId':1,'startDate':a.isoformat(),'endDate':b.isoformat(),
                         'gameTypes':'R,F,D,L,W','hydrate':'linescore'})
            payload=fetcher(API+'?'+q)
            incoming.extend(schedule_from_response(payload,as_of.isoformat()))
    if not incoming:return 0
    data=root/'data';data.mkdir(exist_ok=True,parents=True)
    regular_by_year={}
    post=[]
    prior_post=data/'mlb_postseason_2023_2026.csv'
    if prior_post.exists():
        with prior_post.open(newline='',encoding='utf-8-sig') as f:
            post=list(csv.DictReader(f))
    for r in incoming:
        if r['game_type']=='R':regular_by_year.setdefault(r['year'],[]).append(r)
        else:post.append(r)
    for yr,rows in regular_by_year.items():
        save_merged(data/f'mlb_{yr}_regular.csv',rows)
    if post:save_merged(prior_post,post)
    return len(incoming)


def save_merged(path:Path,incoming:list):
    """Atomic write; duplicate game IDs must have matching identities.

    Allow score correction only when ID/teams/date are identical; MLB may correct runs.
    """
    byid={}
    if path.exists():
        with path.open(newline='',encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                if row.get('game_id'):byid[str(row['game_id'])]=row
    for row in incoming:
        row={k:row.get(k,'') for k in COLUMNS}
        key=str(row['game_id'])
        if key in byid:
            old=byid[key]
            if any(str(old.get(k))!=str(row.get(k)) for k in ('home','away','date')):
                raise ValueError(f'Contradictory ID {key}: team/date mismatch')
        byid[key]=row
    path.parent.mkdir(exist_ok=True,parents=True)
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(byid.values(),key=lambda r:(str(r['date']),str(r['game_id']))))
    tmp.replace(path)
    return len(byid)


def append_future_years(games,root):
    """Existing all_games loader supports 2026; extend cloud to later seasons."""
    import pandas as pd
    import numpy as np
    for f in sorted((root/'data').glob('mlb_20??_regular.csv')):
        year=int(f.name.split('_')[1])
        if year<=2026:continue
        with f.open(newline='',encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r.get('away_final','')=='' or r.get('home_final','')=='':continue
                games.append(dict(date=pd.Timestamp(r['date']),year=year,
                    game_num=str(r['game_id']),game_id='api-'+str(r['game_id']),
                    game_type='R',away=r['away'],home=r['home'],
                    away_final=int(r['away_final']),home_final=int(r['home_final']),
                    away_reg=float(r['away_reg']) if r.get('away_reg') not in ('',None) else np.nan,
                    home_reg=float(r['home_reg']) if r.get('home_reg') not in ('',None) else np.nan,
                    away_sp='',home_sp='',source='MLB Stats API'))
    # The older in-package reader limits postseason data to years <=2026;
    # extend the cloud history for future playoff years without rewriting it.
    postseason=root/'data'/'mlb_postseason_2023_2026.csv'
    if postseason.exists():
        with postseason.open(newline='',encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh):
                if int(r.get('year') or 0)<=2026:continue
                if r.get('away_final','')=='' or r.get('home_final','')=='':continue
                games.append(dict(date=pd.Timestamp(r['date']),year=int(r['year']),
                    game_num=str(r['game_id']),game_id='api-'+str(r['game_id']),
                    game_type='P',away=r['away'],home=r['home'],
                    away_final=int(r['away_final']),home_final=int(r['home_final']),
                    away_reg=float(r['away_reg']) if r.get('away_reg') not in ('',None) else np.nan,
                    home_reg=float(r['home_reg']) if r.get('home_reg') not in ('',None) else np.nan,
                    away_sp='',home_sp='',source='MLB Stats API'))
    games.sort(key=lambda g:(g['year'],g['date'],str(g.get('game_num',''))))
    return games


def all_finals(root:Path):
    results={}
    for f in list((root/'data').glob('mlb_20??_regular.csv'))+[root/'data'/'mlb_postseason_2023_2026.csv']:
        if not f.exists():continue
        with f.open(newline='',encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh):
                if r.get('game_id') and r.get('away_final') not in ('',None) and r.get('home_final') not in ('',None):
                    results[str(r['game_id'])]=r
    return results
