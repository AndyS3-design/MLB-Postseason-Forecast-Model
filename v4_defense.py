"""Optional recent team errors from Retrosheet GL and cached MLB boxscores.

Errors are a crude fielding proxy, NOT Defensive Runs Saved, OAA, or BABIP.
Postgame observations are attached for historical replay ONLY and enter future
forecasts after their game day, never as contemporaneous predictors.
"""
from __future__ import annotations
import csv,json
from pathlib import Path


def add_fielding_errors(games,data_dir):
    data=Path(data_dir)
    old={}
    for yr in (2023,2024,2025):
        p=data/f'GL{yr}.TXT'
        if not p.exists():continue
        with p.open(encoding='latin-1',newline='') as fh:
            for r in csv.reader(fh):
                if len(r)<74:continue
                try:
                    date=str(r[0]);num=str(r[1]);home=r[6];away=r[3]
                    errors=(int(r[73]),int(r[45])) # home, away fielding errors
                    old[(date,num,home,away)]=errors
                except (IndexError,ValueError):continue
    matched=0
    result=[]
    for g in games:
        x=g.copy();d=str(g['date'])[:10].replace('-','')
        key=(d,str(g.get('game_num','')),str(g['home']),str(g['away']))
        if key in old:
            x['home_errors'],x['away_errors']=old[key];matched+=1
        else:
            gid=str(g.get('game_id') or '').removeprefix('api-')
            cache=data/'mlb_boxscores'/f'{gid}.json'
            if gid.isdigit() and cache.exists():
                try:
                    box=json.loads(cache.read_text(encoding='utf-8'))['teams']
                    h=box['home']['teamStats']['fielding']['errors']
                    a=box['away']['teamStats']['fielding']['errors']
                    x['home_errors']=int(h);x['away_errors']=int(a);matched+=1
                except (KeyError,ValueError,TypeError,json.JSONDecodeError):pass
        result.append(x)
    return result,matched
