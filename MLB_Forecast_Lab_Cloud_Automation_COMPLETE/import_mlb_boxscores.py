"""OPTIONAL 2026 MLB box-score enrichment on internet-connected Windows.

Reads previously imported `data/mlb_2026_regular.csv` + playoff CSV, then
fetches actual starters/bullpen pitching stats from MLB Stats API game boxscores.
Finished game dates must precede --through. Caches every successful boxscore.
Unknown/missing data remain missing. This can take several minutes for a season.

  py import_mlb_boxscores.py --through 2026-10-12 --workers 4

This does NOT download pitch-by-pitch handedness-adjusted plate appearances.
Team-vs-starter-hand run production is a coarse proxy, not wRC+.
"""
from __future__ import annotations
import argparse,csv,json,math
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date
from pathlib import Path
from urllib.request import urlopen,Request
from import_retrosheet_details import DETAIL_FIELDS,DIRECTORY_FIELDS,detail_key

API='https://statsapi.mlb.com/api/v1'


def outs_from_ip(value):
    s=str(value or '').strip()
    if not s:return None
    head,point=(s.split('.',1)+[''])[:2]
    if not head.isdigit() or (point and point not in ('0','1','2')):return None
    return int(head)*3+int(point or '0')


def get_games(data_dir,through,start):
    games={}
    for name in ('mlb_2026_regular.csv','mlb_postseason_2023_2026.csv'):
        p=data_dir/name
        if not p.exists():continue
        with p.open(newline='',encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row.get('year')!='2026':continue
                dt=row.get('date','')[:10]
                if start<=dt<through and row.get('game_id','').isdigit():
                    games[row['game_id']]=row
    return list(games.values())


def request_json(url):
    with urlopen(Request(url,headers={'User-Agent':'MLB research analysis / educational 1.0'}),timeout=35) as res:
        return json.load(res)


def pitcher_stats(payload,side,game):
    team=payload.get('teams',{}).get(side,{})
    pitchers=team.get('pitchers') or []
    players=team.get('players') or {}
    if not pitchers:return None,None
    played=[]
    for pid in pitchers:
        player=players.get(f'ID{pid}') or players.get(str(pid),{})
        stats=player.get('stats',{}).get('pitching',{})
        outs=outs_from_ip(stats.get('inningsPitched'))
        if outs is None:continue
        person=player.get('person',{})
        played.append((str(pid),stats,outs,person))
    if not played:return None,None
    pid,stats,outs,person=played[0]
    # Team['pitchers'] is in appearance order; first actual pitcher is starter.
    hand=(person.get('pitchHand') or {}).get('code','').upper()
    if hand not in ('L','R'):hand=''
    def val(s,key):
        try:return int(s.get(key,0) or 0)
        except (ValueError,TypeError):return 0
    row=dict(date=game['date'],home=game['home'],away=game['away'],side=side,
             game_num=str(game.get('game_num') or ''),game_id=str(game.get('game_id') or ''),
             pitcher_id=f'MLB-{pid}',sp_hand=hand,sp_outs=outs,
             sp_er=val(stats,'earnedRuns'),sp_k=val(stats,'strikeOuts'),
             sp_bb=val(stats,'baseOnBalls'),sp_hr=val(stats,'homeRuns'),
             sp_pitches=val(stats,'numberOfPitches') if stats.get('numberOfPitches') is not None else '',
             bp_outs=sum(t[2] for t in played[1:]),
             bp_er=sum(val(t[1],'earnedRuns') for t in played[1:]),
             bp_pitches=sum(val(t[1],'numberOfPitches') for t in played[1:]) if any(t[1].get('numberOfPitches') for t in played[1:]) else '',
             pitchers_used=len(played),manager_id='',manager_name='')
    for c in team.get('coaches') or []:
        if str(c.get('job') or '').lower()=='manager':
            manager=c.get('person') or {}
            row['manager_id']='MLB-MGR-'+str(manager.get('id')) if manager.get('id') else ''
            row['manager_name']=manager.get('fullName','')
            break
    directory=dict(pitcher_id=f'MLB-{pid}',name=person.get('fullName',''),
                   hand=hand,season=2026,team=game[side])
    return row,directory


def one_game(game,cache):
    game_id=game['game_id'];dest=cache/f'{game_id}.json'
    if dest.exists():payload=json.loads(dest.read_text())
    else:
        payload=request_json(f'{API}/game/{game_id}/boxscore')
        # Don't cache malformed responses.
        if not payload.get('teams'):raise ValueError(f'Invalid boxscore {game_id}')
        dest.write_text(json.dumps(payload))
    rows=[];directory=[]
    for side in ('home','away'):
        record,player=pitcher_stats(payload,side,game)
        if record:rows.append(record);directory.append(player)
    if len(rows)!=2:raise ValueError(f'Incomplete pitching lines: game {game_id}')
    return rows,directory


def enrich_missing_pitcher_hands(records,people,data_dir,workers):
    """Fetch only missing immutable pitcher throwing-hand metadata; cache by MLB ID."""
    missing={p['pitcher_id'] for p in people if p['hand'] not in ('L','R')}
    if not missing:return
    cache=data_dir/'mlb_people';cache.mkdir(parents=True,exist_ok=True)
    def fetch_person(pid):
        numeric=pid.removeprefix('MLB-')
        dest=cache/f'{numeric}.json'
        if dest.exists():body=json.loads(dest.read_text())
        else:
            body=request_json(f'{API}/people/{numeric}')
            if not body.get('people'):return pid,''
            dest.write_text(json.dumps(body))
        players=body.get('people') or []
        hand=(players[0].get('pitchHand') or {}).get('code','').upper() if players else ''
        return pid, hand if hand in ('L','R') else ''
    hands={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(fetch_person,pid):pid for pid in missing}
        for f in as_completed(futures):
            try:
                pid,hand=f.result()
                if hand:hands[pid]=hand
            except Exception:continue
    for p in people:
        if p['hand'] not in ('L','R'):p['hand']=hands.get(p['pitcher_id'],'')
    for r in records:
        if r['sp_hand'] not in ('L','R'):r['sp_hand']=hands.get(r['pitcher_id'],'')


def write_merged(data_dir,new_rows,people):
    path=data_dir/'advanced_pitching_details.csv';old=[]
    if path.exists():
        with path.open(newline='',encoding='utf-8') as f:old=list(csv.DictReader(f))
    bykey={detail_key(r):r for r in old}
    for r in new_rows:bykey[detail_key(r)]=r
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=DETAIL_FIELDS,extrasaction='ignore');w.writeheader();w.writerows(bykey.values())
    path=data_dir/'pitcher_directory.csv';old=[]
    if path.exists():
        with path.open(newline='',encoding='utf-8') as f:old=list(csv.DictReader(f))
    bykey={(r['pitcher_id'],str(r['season']),r.get('team','')):r for r in old}
    for r in people:bykey[(r['pitcher_id'],str(r['season']),r['team'])]=r
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=DIRECTORY_FIELDS,extrasaction='ignore');w.writeheader();w.writerows(bykey.values())
    return len(new_rows),len(bykey)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--through',default='2026-10-12',help='Exclusive date; no result from this date or later')
    p.add_argument('--start',default='2026-03-01')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--limit',type=int,default=0,help='Optional first N games for testing')
    p.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'data')
    args=p.parse_args()
    if not (1<=args.workers<=8):p.error('workers must be in 1..8')
    if not (date.fromisoformat(args.start)<date.fromisoformat(args.through)):
        p.error('start must precede through')
    games=sorted(get_games(args.data_dir,args.through,args.start),key=lambda g:(g['date'],g['game_id']))
    if args.limit:games=games[:args.limit]
    if not games:
        print('No 2026 games to enrich. Run `py ingest_mlb.py --as-of 2026-10-12` first.');return
    cache=args.data_dir/'mlb_boxscores';cache.mkdir(parents=True,exist_ok=True)
    rec=[];directory=[];failed=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs={pool.submit(one_game,game,cache):game['game_id'] for game in games}
        for n,future in enumerate(as_completed(jobs),1):
            try:
                r,d=future.result();rec.extend(r);directory.extend(d)
            except Exception as exc:
                failed.append({'game_id':jobs[future],'error':str(exc)[:180]})
            if n%100==0:print(f'Processed {n}/{len(games)} game boxscores',flush=True)
    if rec:
        enrich_missing_pitcher_hands(rec,directory,args.data_dir,args.workers)
        rows,count=write_merged(args.data_dir,rec,directory)
    else:rows=count=0
    summary={'games_requested':len(games),'complete_games_imported':len(rec)//2,
             'pitching_rows_imported':rows,'directory_entries':count,
             'failed_games':failed[:10],'failed_count':len(failed)}
    print(json.dumps(summary,indent=2))
    if not rec:raise RuntimeError('No new pitching data obtained; model data files were not overwritten')

if __name__=='__main__':main()
