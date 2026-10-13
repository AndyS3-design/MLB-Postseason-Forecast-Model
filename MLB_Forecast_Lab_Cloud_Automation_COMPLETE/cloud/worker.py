"""Cloud pregame MLB forecast service — official baseball data only.

Run once on a schedule (GitHub Actions), not as a long-running server.
Immutable forecast files prove cutoff times; settlement is separate.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,subprocess,sys,traceback
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np

from extended_eval import all_games
from forecast_engine import fetch_schedule
from v4_workflow import build_assets,generate
from v4_sources import capture_official_pregame
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only,team_indices
from v6_display import display_forecast
from cloud.refresh import current_season_results,append_future_years,all_finals
from cloud.starter_backfill import backfill_match_starters

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'cloud_records'
ET=ZoneInfo('America/New_York')
MIN_LEAD_MINUTES=8
MAX_LEAD_MINUTES=30
N_SIMULATIONS=12000


def utcnow():return datetime.now(timezone.utc)


def encode_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.temp')
    temp.write_text(json.dumps(obj,indent=2,sort_keys=True,default=str,allow_nan=False),encoding='utf-8')
    temp.replace(path)


def read_json(path,default=None):
    if not path.exists():return default
    return json.loads(path.read_text(encoding='utf-8'))


def sanitize_status(status):
    return str(status or '').strip().lower()


def can_forecast(game,now):
    """Accept ONLY verified scheduled matches within 8–30 minutes of first pitch."""
    if str(game.get('game_type','R')) not in ('R','F','D','L','W'):return False
    try:
        dt=datetime.fromisoformat(str(game.get('start_utc','')).replace('Z','+00:00'))
        if dt.tzinfo is None:return False
        minutes=(dt-now).total_seconds()/60
    except (ValueError,TypeError):return False
    if not MIN_LEAD_MINUTES<=minutes<=MAX_LEAD_MINUTES:return False
    if sanitize_status(game.get('status')) not in ('scheduled','pre-game','pregame','preview','warmup'):
        return False
    return str(game.get('id','')).isdigit() and game.get('away')!=game.get('home')


def latest_data_day(now):return now.astimezone(ET).date()


def new_games(root):
    games=all_games(root/'data',True)
    return append_future_years(games,root)


def initialize_details(root,now,network=True):
    """Best effort one-time Retrosheet pitcher detail import and 2024-only calibration."""
    details=root/'data'/'advanced_pitching_details.csv'
    record=STATE/'bootstrap_status.json'
    previous=read_json(record,{}) or {}
    if not details.exists() and network:
        prev_time=previous.get('last_attempt_utc')
        last=datetime.fromisoformat(prev_time) if prev_time else None
        if last is None or now-last>timedelta(days=3):
            previous={'last_attempt_utc':now.isoformat(),'status':'attempted'}
            encode_json(record,previous)
            try:
                proc=subprocess.run([sys.executable,'import_retrosheet_details.py',
                                     '--years','2023','2024','2025'],cwd=root,
                                     capture_output=True,text=True,timeout=300)
                if proc.returncode!=0:raise RuntimeError((proc.stderr or proc.stdout)[-500:])
                previous.update(status='imported',note='Retrosheet starter history loaded')
            except Exception as exc:
                previous.update(status='unavailable',note=str(exc)[:250])
            encode_json(record,previous)
    calibration=root/'outputs'/'v62_pitcher_calibration.json'
    if not calibration.exists() and details.exists() and details.stat().st_size>100000:
        try:
            proc=subprocess.run([sys.executable,'v62_calibrate.py'],cwd=root,
                                capture_output=True,text=True,timeout=300)
            if proc.returncode!=0:raise RuntimeError((proc.stderr or proc.stdout)[-400:])
            previous.update(calibration='done',calibrated_at_utc=now.isoformat())
        except Exception as exc:
            previous.update(calibration='unavailable',calibration_error=str(exc)[:260])
        encode_json(record,previous)
    return previous


def refresh_recent_boxscores(root,cutoff,max_new=26):
    """Cache actual past boxscores incrementally; never fetch today's current game."""
    try:
        from import_mlb_boxscores import get_games,one_game,write_merged
    except ImportError:return {'status':'importer unavailable'}
    target_start=(cutoff-timedelta(days=65)).isoformat()
    games=get_games(root/'data',cutoff.isoformat(),target_start)
    if not games:return {'status':'no recent final games'}
    cache=root/'data'/'mlb_boxscores';cache.mkdir(exist_ok=True,parents=True)
    # Prioritize recency for current lineups; distinguish cache from merged CSV coverage.
    games=sorted(games,key=lambda x:(x['date'],str(x['game_id'])),reverse=True)
    missing=[g for g in games if not (cache/(str(g['game_id'])+'.json')).exists()][:max_new]
    imported=[];names=[];errors=[]
    for g in missing:
        try:
            rec,people=one_game(g,cache)
            if len(rec)!=2:raise ValueError('No two team pitching records')
            imported.extend(rec);names.extend(people)
        except Exception as exc:errors.append({'game':g['game_id'],'error':str(exc)[:130]})
    if imported:write_merged(root/'data',imported,names)
    # Limit raw, often large files retained in git; model CSV retains old pitching data.
    allowed=set(str(g['game_id']) for g in games[:130])
    for f in cache.glob('*.json'):
        if f.stem not in allowed:f.unlink()
    return {'status':'ok','new_games':len(imported)//2,
            'recent_cached_games':len(list(cache.glob('*.json'))),'errors':errors[:5]}


def game_evidence(game,now):
    try:
        return capture_official_pregame(str(game['id']),str(game['start_utc']),now=now)
    except Exception:
        return None


def store_pregame(game,now,games,root,assets,starter_backfill=None):
    id_=str(game['id']);target=STATE/'predictions'/f'{id_}.json'
    if target.exists():return {'status':'already_frozen','game_id':id_}
    if not can_forecast(game,now):return {'status':'outside_window','game_id':id_}
    day=game['date']
    snap=game_evidence(game,now)
    clean=clean_game_input(game,verified_pregame=True)
    # Important: future events are filtered from the game history and enriched assets.
    prior=pregame_history_only(games,day)
    prior_assets=historical_cutoff_assets(assets,day)
    result=generate(prior,root,day,clean,assets=prior_assets,n=N_SIMULATIONS,
                    official_snapshot=snap,postseason_context_enabled=True,
                    include_2026_snapshot=True)
    f=result['forecast'];score=display_forecast(f,game['away'],game['home'],6.5)
    indices=team_indices(games,day,game['away'],game['home'],data_dir=root/'data')
    start=datetime.fromisoformat(game['start_utc'].replace('Z','+00:00'))
    if now>=start:raise RuntimeError('Forecast finished too late; refusing to freeze')
    g_type='Postseason' if game.get('game_type')!='R' else 'Regular season'
    status={'data_gaps':result['data_gaps'],
            'starter_pitcher_history':result['provenance']['pitcher_coverage'],
            'lineups_confirmed':{s:len(result['personnel'][s]['lineup'])==9 for s in ('home','away')},
            'pitcher_calibrated':bool((root/'outputs'/'v62_pitcher_calibration.json').exists()),
            'official_snapshot_collected':snap is not None,
            'starter_backfill':starter_backfill or {'status':'not performed'},
            'run_model_training_years':assets.get('training_years',[]),
            'run_model_training_coverage':assets.get('coverage_note','not reported')}
    rec=dict(game_id=id_,date=day,game_type=g_type,home=game['home'],away=game['away'],
        home_name=game['home_name'],away_name=game['away_name'],
        starting_pitchers={'home':game.get('home_pitcher') or 'Not announced',
                           'away':game.get('away_pitcher') or 'Not announced'},
        game_start_utc=start.isoformat(),forecast_created_utc=now.isoformat(),
        minutes_before_game=round((start-now).total_seconds()/60,1),
        model_version=result['model_version'],model_commit=os.getenv('GITHUB_SHA','local'),
        model_training_cutoff=result['provenance']['model_frozen_training'],
        features_cutoff_exclusive=day,
        projected_score={'home':score['home_runs'],'away':score['away_runs'],
                         'sum':score['total'],'exact_probability':float(score['chosen_score_probability'])},
        predicted_home_win=float(f['home_win_probability']),
        elo_home_win=float(result['baseline']['elo_home_win']),
        expected_runs={'home':float(f['home_expected_runs']),'away':float(f['away_expected_runs']),
                       'total':float(f['total_expected_runs'])},
        under_6_5_probability=float(f['under_6_5_probability']),
        total_distribution=f['total_pmf'],
        score_grid=f['score_grid'],
        team_indices=indices.get('teams',{}),health=status,
        scenario={'postseason_factor':result['adjustments']['postseason_scoring'].get('factor',1.),
                  'starter_weight':result['adjustments']['starter_total_rate']['weight'],
                  'park_factor':result['adjustments']['park']['factor'],
                  'weather_factor':result['adjustments']['weather']['factor']},
        source='Official MLB pregame schedule; baseball-only model; no market inputs',
        data_quality='LIMITED' if status['data_gaps'] else 'FEATURES AVAILABLE')
    encode_json(target,rec)
    return {'status':'saved','game_id':id_,'away':rec['away'],'home':rec['home'],
            'minutes_before_game':rec['minutes_before_game']}


def settle(root):
    finals=all_finals(root)
    changed=0
    for f in sorted((STATE/'predictions').glob('*.json')):
        rec=read_json(f)
        if rec.get('official_final') or rec.get('game_id') not in finals:continue
        g=finals[rec['game_id']]
        if (g['date']!=rec['date'] or g['away']!=rec['away'] or g['home']!=rec['home']):
            raise ValueError(f'Game identity conflict for {rec["game_id"]}')
        actual_h=int(g['home_final']);actual_a=int(g['away_final'])
        p=float(rec['predicted_home_win']);y=int(actual_h>actual_a)
        rec['official_final']={'home':actual_h,'away':actual_a,
            'settled_at_utc':utcnow().isoformat(),'source':'Official MLB schedule API'}
        rec['evaluation']={'correct_winner':(p>=.5)==bool(y),
            'winner_brier':(p-y)**2,
            'elo_brier':(float(rec['elo_home_win'])-y)**2,
            'abs_run_error_per_team':(abs(actual_h-rec['expected_runs']['home'])+
                                       abs(actual_a-rec['expected_runs']['away']))/2,
            'abs_total_error':abs(actual_h+actual_a-rec['expected_runs']['total']),
            'under_6_5_brier':(float(rec['under_6_5_probability'])-int(actual_h+actual_a<=6))**2}
        encode_json(f,rec);changed+=1
    return changed


def prospective_metrics(records):
    evaluated=[r for r in records if r.get('evaluation')]
    if not evaluated:return {'settled_games':0,'status':'Awaiting prospective results'}
    e=[r['evaluation'] for r in evaluated];n=len(e)
    brier=np.array([x['winner_brier'] for x in e]);base=np.array([x['elo_brier'] for x in e]);
    err=np.array([x['abs_run_error_per_team'] for x in e]);
    result=dict(settled_games=n,accuracy=round(float(np.mean([x['correct_winner'] for x in e])),4),
        winner_brier=round(float(brier.mean()),5),elo_brier=round(float(base.mean()),5),
        run_mae_per_team=round(float(err.mean()),3),
        under_6_5_brier=round(float(np.mean([x['under_6_5_brier'] for x in e])),5),
        status='Insufficient games for uncertainty interval' if n<30 else 'Confidence interval available')
    if n>=30:
        delta=base-brier
        # Grouped resampling by game DATE, not individual bets; avoid fake precision.
        bydate={}
        for r in evaluated:bydate.setdefault(r['date'],[]).append(r['evaluation']['elo_brier']-r['evaluation']['winner_brier'])
        d=list(bydate);rng=np.random.default_rng(2026)
        boot=[]
        for _ in range(1000):
            dates=rng.choice(d,len(d),replace=True)
            vals=[v for day in dates for v in bydate[day]]
            boot.append(float(np.mean(vals)))
        result['elo_minus_model_brier_95_ci']=[round(float(x),5) for x in np.percentile(boot,[2.5,97.5])]
        result['elo_minus_model_brier']=round(float(delta.mean()),5)
        result['statistically_distinguishable_from_elo']=not(result['elo_minus_model_brier_95_ci'][0]<=0<=result['elo_minus_model_brier_95_ci'][1])
    return result


def render_site(root,now,summary):
    import shutil
    entries=[]
    for f in (STATE/'predictions').glob('*.json'):
        try:entries.append(read_json(f))
        except (ValueError,TypeError):pass
    entries.sort(key=lambda r:(r.get('game_start_utc',''),r.get('game_id','')),reverse=True)
    output={'updated_utc':now.isoformat(),
        'local_timezone':'America/New_York',
        'predictions':entries[:350],
        'prospective_performance':prospective_metrics(entries),
        'operations':summary,
        'disclaimer':'Baseball-only research forecast. Past outcome never enters a pregame prediction. Unverified advanced inputs are marked missing.'}
    site=root/'site';site.mkdir(exist_ok=True,parents=True)
    encode_json(site/'data.json',output)
    if not (site/'index.html').exists():raise FileNotFoundError('site/index.html missing')
    (site/'.nojekyll').touch()
    return len(entries)


def run(root=ROOT,now=None,network=True,fast=False):
    root=Path(root);now=now or utcnow();STATE.mkdir(parents=True,exist_ok=True)
    (STATE/'predictions').mkdir(exist_ok=True,parents=True)
    summary={'run_started_utc':now.isoformat(),'status':'in progress','events':[]}
    today=latest_data_day(now)
    if network and not fast:
        try:
            from cloud.history_bootstrap import ensure_history
            summary["historical_game_logs"]=ensure_history(root/"data")
        except Exception as exc:
            summary["events"].append(f"Historical game logs unavailable: {str(exc)[:160]}")
        try:
            count=current_season_results(root,today)
            summary['refreshed_finished_games']=count
        except Exception as exc:summary['events'].append(f'Official results refresh unavailable: {str(exc)[:170]}')
        try:
            summary['pitching_import_status']=initialize_details(root,now)
        except Exception as exc:summary['events'].append(f'Historical pitcher import unavailable: {str(exc)[:160]}')
        try:
            summary['recent_boxscores']=refresh_recent_boxscores(root,today)
        except Exception as exc:summary['events'].append(f'Recent boxscores unavailable: {str(exc)[:160]}')
    games=None;assets=None
    candidate_games=[]
    if network:
        for offset in ((0,1) if fast else (-1,0,1)):
            dt=now.astimezone(ET).date()+timedelta(days=offset)
            if dt.year<2026:continue
            try:candidate_games+=fetch_schedule(dt)
            except Exception as exc:summary['events'].append(f'Schedule unavailable for {dt}: {str(exc)[:130]}')
    seen_ids=set()
    upcoming=[]
    for match in candidate_games:
        gid=str(match.get('id') or '')
        if gid in seen_ids or not can_forecast(match,now):
            continue
        seen_ids.add(gid)
        if (STATE/'predictions'/f'{gid}.json').exists():
            continue
        upcoming.append(match)
    # Run targeted official starter-history import *before* building model assets;
    # otherwise pitcher statistics added during this run would be invisible to
    # the current forecast. Strict previous-day cutoff applies to all imports.
    backfills={}
    if network:
        for match in upcoming:
            try:
                backfills[str(match['id'])]=backfill_match_starters(
                    root/'data',match,match['date'])
            except Exception as exc:
                backfills[str(match['id'])]={'status':'unavailable',
                    'error':str(exc)[:180]}
    if backfills:
        summary['starter_history_backfill']=backfills
    for match in upcoming:
        try:
            if games is None:
                games=new_games(root)
                assets=build_assets(games,root)
            summary['events'].append(store_pregame(
                match,utcnow() if network else now,games,root,assets,
                starter_backfill=backfills.get(str(match['id']))))
        except Exception as exc:
            summary['events'].append({'status':'forecast_failed','game_id':match['id'],
                                      'error':str(exc)[:180]})
    summary['new_settlements']=settle(root)
    summary['status']='finished'
    summary['known_pre_game_records']=render_site(root,now,summary)
    encode_json(STATE/'last_run.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','render','calibrate'])
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--fast',action='store_true',help='Pregame only: skip expensive data refresh')
    args=parser.parse_args()
    if args.command=='run':result=run(network=not args.offline,fast=args.fast)
    elif args.command=='render':
        result={'known_records':render_site(ROOT,utcnow(),{'status':'render only'})}
    else:
        result=initialize_details(ROOT,utcnow(),network=not args.offline)
    print(json.dumps(result,indent=2,default=str))

if __name__=='__main__':main()
