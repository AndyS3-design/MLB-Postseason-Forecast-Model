#!/usr/bin/env python3
"""Acquire MLB season and postseason schedules through official Stats API or saved JSON.

No baseball predictions are made by this module. Games still in progress,
postponed games, and games after --as-of are not incorporated.
MLB API: https://statsapi.mlb.com/api/v1/schedule
"""
import argparse
import csv
import json
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API='https://statsapi.mlb.com/api/v1/schedule'
# Translate MLB official franchise IDs to Retrosheet game-log three-letter codes.
MLB_TO_RETRO={
 108:'ANA',109:'ARI',110:'BAL',111:'BOS',112:'CHN',113:'CIN',114:'CLE',115:'COL',
 116:'DET',117:'HOU',118:'KCA',119:'LAN',120:'WAS',121:'NYN',133:'OAK',134:'PIT',
 135:'SDN',136:'SEA',137:'SFN',138:'SLN',139:'TBA',140:'TEX',141:'TOR',142:'MIN',
 143:'PHI',144:'ATL',145:'CHA',146:'MIA',147:'NYA',158:'MIL'
}
COLUMNS=['game_id','date','first_pitch_utc','year','game_type','away','home','away_final',
         'home_final','away_reg','home_reg','away_sp','home_sp','source']


def schedule_from_response(payload,as_of='2026-10-12'):
    """Parse schedule JSON; return ONLY completed games played before the as-of date.

    as_of represents an exclusive *game-date* cutoff, NOT an intraday prediction time.
    For in-progress 'today' use the previous date as a cutoff; no live data leaked.
    """
    rows=[]
    cutoff=date.fromisoformat(as_of)
    for block in payload.get('dates',[]):
        for g in block.get('games',[]):
            d=date.fromisoformat(g.get('officialDate') or block['date'])
            if d>=cutoff:continue
            status=g.get('status',{})
            if status.get('abstractGameState')!='Final':continue
            kind=g.get('gameType','')
            if kind not in ('R','P','F','D','L','W'):continue
            teams=g.get('teams',{})
            # Some MLB API entries report abstractGameState='Final' but do not
            # include scores (for example, archived or administratively ended
            # fixtures). Such entries cannot be training examples: skip them
            # explicitly instead of crashing or inventing 0-0 scores.
            try:
                home=teams['home'];away=teams['away']
                hs=int(home['score']);a=int(away['score'])
            except (KeyError,TypeError,ValueError) as exc:
                warnings.warn(
                    f"Skipping final game {g.get('gamePk')}: missing/invalid team score; "
                    "no result was imputed.", RuntimeWarning, stacklevel=2
                )
                continue
            try:
                ht=MLB_TO_RETRO[home['team']['id']];at=MLB_TO_RETRO[away['team']['id']]
                game_id=int(g['gamePk'])
                played=datetime.fromisoformat(g['gameDate'].replace('Z','+00:00'))
            except (KeyError,TypeError,ValueError) as exc:
                raise ValueError(f'Final game has missing team ID or timestamp: {g.get("gamePk")}') from exc
            if hs==a:raise ValueError(f'Final game incorrectly tied {game_id}')
            # Breakdown by innings is needed for a predictive regulation-runs model.
            # When linescore is absent, keep final results but leave reg runs blank;
            # NEVER fill regulation values from final on an extra-inning game.
            linescore=g.get('linescore') or {}
            innings=linescore.get('innings') or []
            if len(innings)>=9:
                ra=sum(int(x.get('away',{}).get('runs') or 0) for x in innings[:9])
                rh=sum(int(x.get('home',{}).get('runs') or 0) for x in innings[:9])
            else:
                current_inning=linescore.get('currentInning')
                # Don't assume an unknown number of innings means regulation.
                ra=a if isinstance(current_inning,int) and current_inning<=9 else None
                rh=hs if isinstance(current_inning,int) and current_inning<=9 else None
            # Probable pitcher is NOT necessarily actual starter; do not use in training.
            rows.append(dict(game_id=game_id,date=d.isoformat(),first_pitch_utc=played.isoformat(),
                  year=d.year,game_type=kind,away=at,home=ht,away_final=a,home_final=hs,
                  away_reg=ra,home_reg=rh,away_sp='',home_sp='',source='MLB Stats API'))
    return rows


def monthly_ranges(year,game_type,as_of):
    start=date(year,3,1) if game_type=='R' else date(year,9,1)
    end=min(date(year,12,1),date.fromisoformat(as_of))
    while start<end:
        stop=min(date(start.year+(start.month==12),(start.month%12)+1,1),end)
        yield start,(stop-timedelta(days=1))
        start=stop


def fetch(year,kind,as_of,raw_dir):
    out=[]
    for start,end in monthly_ranges(year,kind,as_of):
        params={'sportId':1,'startDate':start.isoformat(),'endDate':end.isoformat(),
                'gameTypes':('F,D,L,W' if kind=='P' else kind),'hydrate':'linescore'}
        url=API+'?'+urlencode(params)
        dest=raw_dir/f'mlb_{year}_{kind}_{start.isoformat()}.json'
        if dest.exists():
            payload=json.loads(dest.read_text())
        else:
            req=Request(url,headers={'User-Agent':'Research MLB backtest / 1.0'})
            try:
                with urlopen(req,timeout=25) as f:payload=json.load(f)
            except Exception as exc:
                raise RuntimeError(f'Unable to fetch {url}: {exc}. Download the schedule JSON '
                    f'via browser and save it as {dest.name} in {raw_dir}.') from exc
            dest.write_text(json.dumps(payload))
        out.extend(schedule_from_response(payload,as_of))
    return out


def ingest_cached(raw_dir,as_of):
    out=[]
    for f in sorted(raw_dir.glob('*.json')):
        if f.name.startswith('mlb_') or f.name.startswith('schedule_'):
            payload=json.loads(f.read_text())
            out.extend(schedule_from_response(payload,as_of))
    return out


def save(rows,dest):
    by_id={}
    for r in rows:
        key=r['game_id']
        if key in by_id:
            prior=by_id[key]
            if any(prior[k]!=r[k] for k in ('home','away','home_final','away_final','date')):
                raise ValueError(f'Contradictory results for game {key}')
        by_id[key]=r
    clean=sorted(by_id.values(),key=lambda r:(r['date'],r['game_id']))
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(clean)
    return len(clean)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--as-of',default='2026-10-12',help='Exclusive game date: include through previous day')
    p.add_argument('--raw-dir',type=Path,default=Path(__file__).parent/'data'/'mlb_api_json')
    p.add_argument('--out-dir',type=Path,default=Path(__file__).parent/'data')
    p.add_argument('--offline',action='store_true',help='Only parse MLB API JSON already saved')
    args=p.parse_args()
    args.raw_dir.mkdir(exist_ok=True,parents=True)
    if args.offline: rows=ingest_cached(args.raw_dir,args.as_of)
    else:
        rows=[]
        for yr in [2023,2024,2025,2026]:
            if str(yr)>args.as_of[:4]:continue
            for t in (['P'] if yr<2026 else ['R','P']):
                rows.extend(fetch(yr,t,args.as_of,args.raw_dir))
    if not rows:
        print('DATA UNAVAILABLE: no MLB API schedule JSON found; existing files have NOT been overwritten.')
        return
    nreg=save([r for r in rows if r['game_type']=='R' and r['year']==2026],args.out_dir/'mlb_2026_regular.csv')
    npost=save([r for r in rows if r['game_type']!='R'],args.out_dir/'mlb_postseason_2023_2026.csv')
    print(json.dumps({'2026_regular_games':nreg,'postseason_games':npost,'as_of_exclusive':args.as_of},indent=2))

if __name__=='__main__':main()
