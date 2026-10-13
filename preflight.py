"""Cheap (stdlib-only) MLB pregame gate for GitHub Actions.

The expensive forecasting job runs only when a first pitch is getting close,
when explicitly requested, or during the daily maintenance run. Cron timing is
best-effort; the forecasting worker independently checks the actual cutoff.
"""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from pathlib import Path

API='https://statsapi.mlb.com/api/v1/schedule'
MIN_LEAD_MINUTES=16
MAX_LEAD_MINUTES=31
GAME_TYPES={'R','F','D','L','W'}
ALLOWED_STATES={'preview','pre-game','pregame','scheduled','warmup'}

def find_approaching_games(now,fetcher=None):
    if fetcher is None:fetcher=fetch_schedule
    matches=[]
    # UTC dates avoid missing a game in another local timezone, including DST.
    for day in {now.date(),(now+timedelta(days=1)).date()}:
        payload=fetcher(day)
        for block in payload.get('dates',[]):
            for game in block.get('games',[]):
                if game.get('gameType') not in GAME_TYPES:continue
                state=str(game.get('status',{}).get('detailedState','')).lower()
                if state not in ALLOWED_STATES:continue
                try:
                    start=datetime.fromisoformat(game['gameDate'].replace('Z','+00:00'))
                    lead=(start-now).total_seconds()/60
                except (ValueError,KeyError,TypeError):continue
                if MIN_LEAD_MINUTES<=lead<=MAX_LEAD_MINUTES:
                    matches.append({'id':str(game.get('gamePk','')),
                                    'starts_utc':start.isoformat(),
                                    'lead_minutes':round(lead,1)})
    return matches

def fetch_schedule(day):
    q=urlencode({'sportId':1,'date':day.isoformat(),'gameTypes':','.join(sorted(GAME_TYPES))})
    with urlopen(Request(API+'?'+q,headers={'User-Agent':'MLB Forecast Lab scheduling / 1.0'}),timeout=12) as f:
        return json.load(f)

def should_run(now,manual=False,maintenance=False,fetcher=None):
    if manual:return {'run':True,'reason':'manually triggered','approaching_games':[]}
    if maintenance:return {'run':True,'reason':'daily maintenance','approaching_games':[]}
    try:
        matches=find_approaching_games(now,fetcher)
    except Exception as exc:
        # Fail closed. The next scheduled gate will retry, no fabricated matchups.
        return {'run':False,'reason':'schedule fetch failed: '+str(exc)[:140], 'approaching_games':[]}
    return {'run':bool(matches),'reason':'pregame window' if matches else 'no approaching games',
            'approaching_games':matches}

def main():
    p=argparse.ArgumentParser();p.add_argument('--github-output',type=Path)
    p.add_argument('--manual',action='store_true');p.add_argument('--maintenance',action='store_true')
    args=p.parse_args();now=datetime.now(timezone.utc)
    result=should_run(now,args.manual,args.maintenance)
    print(json.dumps({'now_utc':now.isoformat(),**result},indent=2))
    if args.github_output:
        with args.github_output.open('a',encoding='utf-8') as f:
            f.write('run_model='+('true' if result['run'] else 'false')+'\n')
            f.write('mode='+('full' if args.manual or args.maintenance else 'pregame')+'\n')

if __name__=='__main__':main()
