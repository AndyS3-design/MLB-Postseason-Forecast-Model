"""Explicitly requested night-before MLB forecasts, research stage only.

2026-10-15 games are simulated now from verified official future schedule
and earlier-date baseball records. Outputs are GitHub Actions artifacts, NOT
official final 8–30 minute originals or tomorrow's frozen day-of preliminaries.
No forecast already saved to the dashboard is modified.
"""
from __future__ import annotations

import json
from datetime import date,datetime,timezone
from pathlib import Path

from cloud.worker import (ROOT,new_games,fetch_schedule,N_SIMULATIONS,
                          current_season_results)
from cloud.starter_backfill import backfill_match_starters
from cloud.official_hitter_history import collect_verified_lineup_history
from v4_sources import capture_official_pregame
from v4_workflow import build_assets,generate
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only
from v6_baseball_totals import half_run_line_probabilities

GAME_DAY=date(2026,10,15)
EXPECTED={'849818','849810'}
ALLOWED={'scheduled','pre-game','pregame','preview','warmup','warmups'}


def utcnow():
    return datetime.now(timezone.utc)


def main():
    now=utcnow()
    if now.date()>GAME_DAY:
        raise RuntimeError('Refusing to retrospectively generate an October 15 early preview')
    matches=fetch_schedule(GAME_DAY)
    matches=[m for m in matches if str(m.get('id')) in EXPECTED]
    seen={str(m['id']) for m in matches}
    if seen!=EXPECTED or len(matches)!=2:
        raise RuntimeError(f'Official schedule cannot confirm both exact game IDs: got {sorted(seen)}')
    print('OFFICIAL_FIXTURES',json.dumps([
      {k:m.get(k) for k in ('id','date','away','home','away_name','home_name',
                           'start_utc','status','away_pitcher','home_pitcher')}
      for m in matches],default=str),flush=True)
    if any(m.get('date')!=GAME_DAY.isoformat() or
           str(m.get('status') or '').lower().strip() not in ALLOWED or
           datetime.fromisoformat(m['start_utc'].replace('Z','+00:00'))<=now
           for m in matches):
        raise RuntimeError('Official game date/status not future; refuse a fake pregame preview')

    # Optional verified current-season past *final* games, never a live score.
    # No post-10/15 data are available to model features: chronological
    # pregame_history_only and historical_cutoff_assets enforce the cutoff.
    try:
        imports=current_season_results(ROOT,GAME_DAY)
        print('PRIOR_FINALS_IMPORT',imports,flush=True)
    except Exception as exc:
        print('PRIOR_FINALS_IMPORT_UNAVAILABLE',repr(exc)[:260],flush=True)
    backfill={}
    for m in matches:
        try:
            backfill[str(m['id'])]=backfill_match_starters(ROOT/'data',m,GAME_DAY.isoformat())
            print('PRIOR_STARTER_BACKFILL',m['id'],json.dumps(backfill[str(m['id'])],default=str)[:800],flush=True)
        except Exception as exc:
            backfill[str(m['id'])]={'status':'unavailable','error':str(exc)[:190]}
            print('PRIOR_STARTER_UNAVAILABLE',m['id'],repr(exc)[:160],flush=True)

    history=new_games(ROOT)
    assets=build_assets(history,ROOT)
    cutoff_games=pregame_history_only(history,GAME_DAY.isoformat())
    cutoff_assets=historical_cutoff_assets(assets,GAME_DAY.isoformat())
    outputs=[]
    for m in matches:
        before=utcnow()
        first_pitch=datetime.fromisoformat(m['start_utc'].replace('Z','+00:00'))
        if before>=first_pitch:raise RuntimeError('First pitch already passed')
        snapshot=None
        try:
            snapshot=capture_official_pregame(str(m['id']),m['start_utc'],now=before)
        except Exception as exc:
            print('OFFICIAL_SNAPSHOT_UNAVAILABLE',m['id'],repr(exc)[:220],flush=True)
        official_orders=(snapshot or {}).get('is_official_lineup') or {}
        histories={'status':'no_complete_official_lineups','by_side':{}}
        if all(official_orders.get(side,False) for side in ('away','home')):
            try:
                histories=collect_verified_lineup_history(snapshot,GAME_DAY.isoformat())
            except Exception as exc:
                print('HITTER_HISTORY_UNAVAILABLE',m['id'],repr(exc)[:200],flush=True)
        sim=generate(cutoff_games,ROOT,GAME_DAY.isoformat(),
          clean_game_input(m,verified_pregame=True),
          assets=cutoff_assets,n=N_SIMULATIONS,
          official_snapshot=snapshot,
          official_lineup_history=histories.get('by_side'),
          postseason_context_enabled=True,include_2026_snapshot=True)
        done=utcnow()
        if done>=first_pitch:
            raise RuntimeError('Computation crossed scheduled first pitch; no research preview')
        f=sim['forecast']
        ph=float(f['home_win_probability'])
        side='home' if ph>=.5 else 'away'
        pick=m[side+'_name']
        fav=f.get('favorite_aligned_score')
        exact=f['v6_display_score']
        totals=half_run_line_probabilities(f['total_pmf'])
        row={
           'forecast_kind':'overnight_research_preliminary',
           'not_an_official_final_prediction':True,
           'not_a_frozen_day_of_preliminary':True,
           'game_id':str(m['id']),'game_date':m['date'],
           'away_team':m['away_name'],'home_team':m['home_name'],
           'away_abbr':m['away'],'home_abbr':m['home'],
           'scheduled_first_pitch_utc':first_pitch.isoformat(),
           'forecast_started_utc':before.isoformat(),
           'forecast_finished_utc':done.isoformat(),
           'model_version':sim['model_version'],
           'simulation_count':f['simulation_size'],
           'winner_pick':pick,
           'winner_probability':round(max(ph,1-ph),6),
           'home_win_probability':round(ph,6),
           'away_win_probability':round(1-ph,6),
           'favorite_aligned_score':fav,
           'unconditional_most_common_score':exact,
           'expected_runs':{'home':round(float(f['home_expected_runs']),4),
                             'away':round(float(f['away_expected_runs']),4),
                             'total':round(float(f['total_expected_runs']),4)},
           'total_run_odds':totals,
           'confirmed_lineups':official_orders,
           'official_pregame_source':(snapshot or {}).get('source','unavailable'),
           'starting_pitchers':{'home':m.get('home_pitcher') or 'Not announced',
                                 'away':m.get('away_pitcher') or 'Not announced'},
           'starter_history_backfill':backfill.get(str(m['id'])),
           'verified_hitter_history_status':histories.get('status'),
           'model_data_gaps':sim.get('data_gaps',[]),
           'warning':'OVERNIGHT research only. Lineups and pitchers may change. This is not the immutable final forecast, does not establish a betting edge, and is not the probability of any joint winner+total bet.'
        }
        outputs.append(row)
        print('OVERNIGHT_GAME_FORECAST',json.dumps(row,allow_nan=False,default=str),flush=True)
    payload={'generated_utc':utcnow().isoformat(),
             'stage':'night_before_research_preliminary',
             'model_commit':'night_before_branch_parent_V20',
             'date':'2026-10-15','games':outputs}
    outfile=ROOT/'outputs'/'oct15_two_game_overnight_v20_research.json'
    outfile.parent.mkdir(exist_ok=True)
    outfile.write_text(json.dumps(payload,indent=2,allow_nan=False,default=str)+'\n')
    print('OVERNIGHT_TWO_GAME_FORECAST_COMPLETE',str(outfile),flush=True)


if __name__=='__main__':
    main()
