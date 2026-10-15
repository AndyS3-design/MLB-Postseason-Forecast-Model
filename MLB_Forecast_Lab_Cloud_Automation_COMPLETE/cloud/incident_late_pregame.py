"""One-time, observational late-pregame research forecast: NEVER an official original.

Only if MLB's LIVE feed still shows warmups AND no plate appearances exist,
before and after simulation. Actual UTC wall time is kept, not backdated.
"""
from __future__ import annotations
import json,os
from pathlib import Path
from datetime import datetime,date,timezone
from urllib.request import Request,urlopen

from cloud import worker
from cloud.official_hitter_history import collect_verified_lineup_history
from v4_workflow import build_assets,generate
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only
from v6_baseball_totals import half_run_line_probabilities

ROOT=Path(__file__).resolve().parents[1]
GAME_ID="849811"
URL=f"https://statsapi.mlb.com/api/v1.1/game/{GAME_ID}/feed/live"
def utcnow():return datetime.now(timezone.utc)

def evidence():
    req=Request(URL,headers={'User-Agent':'MLB Forecast Lab official live incident/1.0'})
    with urlopen(req,timeout=20) as response:raw=json.load(response)
    status=(raw.get('gameData') or {}).get('status') or {}
    abstract=str(status.get('abstractGameState') or '').lower()
    detail=str(status.get('detailedState') or '').lower().strip()
    plays=((raw.get('liveData') or {}).get('plays') or {}).get('allPlays') or []
    current=((raw.get('liveData') or {}).get('plays') or {}).get('currentPlay') or {}
    linescore=(raw.get('liveData') or {}).get('linescore') or {}
    no_play=not plays and not current and not linescore.get('currentInning') and not linescore.get('inningState')
    allowed=(abstract in ('preview','pre-game') and
             detail in ('pre-game','pregame','warmup','warmups','scheduled','preview') and no_play)
    return raw,{'utc':utcnow().isoformat(),'game_id':GAME_ID,
        'detailed':status.get('detailedState'),'abstract':status.get('abstractGameState'),
        'coded_state':status.get('codedGameState'),
        'completed_at_bats':len(plays),'current_play':bool(current),
        'inning':linescore.get('currentInning'),'still_pregame':allowed}

def snapshot_from_raw(raw,now):
    live=raw.get('liveData') or {}
    box=(live.get('boxscore') or {}).get('teams') or {}
    meta=raw.get('gameData') or {}
    people=meta.get('players') or {}
    lineups={}
    for side in ('home','away'):
        team=box.get(side) or {}
        players=team.get('players') or {}
        lineup=[]
        for pid in team.get('battingOrder') or []:
            entry=players.get('ID'+str(pid)) or {}
            person=entry.get('person') or {}
            common=people.get('ID'+str(pid)) or {}
            player_id=person.get('id') or common.get('id')
            if str(player_id)!=str(pid):continue
            hand=((entry.get('batSide') or common.get('batSide') or {}).get('code') or '').upper()
            lineup.append({'id':int(pid),'name':person.get('fullName') or common.get('fullName') or str(pid),
                           'batting_hand':hand if hand in ('L','R','S') else ''})
        lineups[side]=lineup
    weather=meta.get('weather') or {}
    return {'game_id':GAME_ID,'captured_utc':now.isoformat(),
       'source':'MLB Stats API live feed verified before actual first pitch (late pregame research)',
       'confirmed_lineups':lineups,
       'is_official_lineup':{s:len(lineups[s])==9 for s in ('home','away')},
       'bullpen_ids':{s:list((box.get(s) or {}).get('bullpen') or []) for s in ('home','away')},
       'weather':{'temp':weather.get('temp'),'wind':weather.get('wind'),'condition':weather.get('condition')},
       'venue':(meta.get('venue') or {}).get('name','Unknown'),'game_status':'Pre-Game'}

def main():
    raw,pre=evidence()
    print('OFFICIAL_START_STATUS',json.dumps(pre),flush=True)
    if not pre['still_pregame']:
        print('STOP: actual game may be underway; no new pregame research forecast generated.',flush=True)
        return
    start_wall=utcnow()
    snap=snapshot_from_raw(raw,start_wall)
    games=worker.new_games(ROOT)
    model=build_assets(games,ROOT)
    # Use official (current as-of) schedule for teams and opposing starters.
    candidates=worker.fetch_schedule(date(2026,10,14))
    match=next((g for g in candidates if str(g.get('id'))==GAME_ID),None)
    if not match:raise RuntimeError('Official game schedule missing; refusing to guess teams')
    if str(match.get('status','')).strip().lower() not in ('pre-game','pregame','preview','scheduled','warmup','warmups'):
        print('STOP: schedule now says game started; no forecast',flush=True);return
    by_day=pregame_history_only(games,match['date'])
    cutoff_assets=historical_cutoff_assets(model,match['date'])
    batter=collect_verified_lineup_history(snap,match['date']) if all(snap['is_official_lineup'].values()) else {'by_side':{},'status':'lineups_incomplete'}
    sim=generate(by_day,ROOT,match['date'],clean_game_input(match,verified_pregame=True),
        assets=cutoff_assets,n=12000,official_snapshot=snap,
        official_lineup_history=batter.get('by_side'))
    _,after=evidence()
    print('OFFICIAL_END_STATUS',json.dumps(after),flush=True)
    if not after['still_pregame']:
        print('STOP: game started before simulation finished. Discarding result; NO backdating.',flush=True)
        return
    f=sim['forecast']
    result={
       'research_only':True,'kind':'late_pregame_research_not_original',
       'warning':'NOT official frozen original, V18 unmerged research branch; do NOT count in prospectively timed 8–30-minute baseline.',
       'game_id':GAME_ID,'game':f"{match['away_name']} at {match['home_name']}",
       'actual_started_utc':start_wall.isoformat(),
       'actual_finished_utc':utcnow().isoformat(),
       'official_status_at_start':pre,'official_status_at_end':after,
       'model':sim['model_version'],
       'confirmed_nine_batter_lineups':snap['is_official_lineup'],
       'full_hitter_history_status':batter.get('status'),
       'away_win_probability':round(float(1-f['home_win_probability']),6),
       'home_win_probability':round(float(f['home_win_probability']),6),
       'expected_combined_runs':round(float(f['total_expected_runs']),4),
       'away_expected_runs':round(float(f['away_expected_runs']),4),
       'home_expected_runs':round(float(f['home_expected_runs']),4),
       'highest_probability_exact_score':f['v6_display_score'],
       'over_under_lines':half_run_line_probabilities(f['total_pmf'])
    }
    out=ROOT/'outputs'/'incident_late_pregame_849811.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('LATE_PREGAME_RESEARCH_FORECAST',json.dumps(result,allow_nan=False),flush=True)

if __name__=='__main__':main()
