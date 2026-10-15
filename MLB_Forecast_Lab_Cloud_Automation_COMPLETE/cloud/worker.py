"""Cloud pregame MLB forecast service — official baseball data only.

Run once on a schedule (GitHub Actions), not as a long-running server.
Immutable forecast files prove cutoff times; settlement is separate.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,subprocess,sys,traceback
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from time import monotonic
from zoneinfo import ZoneInfo
import numpy as np

from extended_eval import all_games
from forecast_engine import fetch_schedule
from v4_workflow import build_assets,generate
from v4_sources import capture_official_pregame
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only,team_indices
from v6_display import display_forecast
from v6_baseball_totals import half_run_line_probabilities
from cloud.refresh import current_season_results,append_future_years,all_finals
from cloud.starter_backfill import backfill_match_starters
from cloud.v8_bullpen_health import matchup_workload
from cloud.v8_evaluate import from_files as prospective_health_report
from cloud.v8_challengers import save_shadow_forecasts,attach_shadows,evaluate_pair as challenger_metrics
from cloud.v9_tracking import summarize as prospective_capture_report
from cloud.v10_schedule_audit import reconcile as official_schedule_reconciliation
from cloud.two_stage import eligible_preliminary, paired_stage_metrics
from cloud.v17_prospective import score_originals as evaluate_full_distribution
from cloud.v8_evaluate import valid_original
from cloud.preflight import official_schedule_days
from cloud.official_hitter_history import collect_verified_lineup_history
from v4_matchup_core import VERSION

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


def can_preliminary(game,now):
    """An early, explicitly provisional GAME-DAY forecast, not the final."""
    return (game.get('home') != game.get('away') and
            eligible_preliminary(game.get('id'),game.get('date'),
                game.get('start_utc'),game.get('game_type','R'),game.get('status'),now))


def can_revise(game,now,original):
    """Accept one revised, independently timestamped PRE-game snapshot."""
    if not original or str(original.get('game_id'))!=str(game.get('id')):return False
    if str(game.get('date'))!=str(original.get('date')):return False
    if game.get('home')!=original.get('home') or game.get('away')!=original.get('away'):return False
    if str(game.get('game_type','R')) not in ('R','F','D','L','W'):return False
    if sanitize_status(game.get('status')) not in ('scheduled','pre-game','pregame','preview','warmup'):return False
    try:
        start=datetime.fromisoformat(str(game['start_utc']).replace('Z','+00:00'))
        first=datetime.fromisoformat(str(original['forecast_created_utc']).replace('Z','+00:00'))
        mins=(start-now).total_seconds()/60
    except (ValueError,TypeError,KeyError):return False
    return first<now and 12<=mins<=150

def revision_requested(root,game):
    path=Path(root)/'cloud_records'/'revision_requests'/f"{game.get('id')}.json"
    try:
        request=read_json(path,{}) or {}
        return (request.get('game_id')==str(game.get('id')) and
                request.get('date')==str(game.get('date')) and
                request.get('kind')=='one_time_pregame_revision')
    except (OSError,ValueError,TypeError):return False

def preliminary_update_requested(root,game,preview):
    """Explicit, version-gated, one-time update without touching frozen early."""
    path=Path(root)/'cloud_records'/'preliminary_update_requests'/f"{game.get('id')}.json"
    try:
        req=read_json(path,{}) or {}
        return (bool(preview)
            and req.get('game_id')==str(game.get('id'))
            and req.get('date')==str(game.get('date'))
            and req.get('kind')=='one_time_preliminary_update'
            and req.get('required_model_version')==VERSION
            and preview.get('model_version')!=VERSION
            and all(str(preview.get(k))==str(game.get(k))
                    for k in ('date','home','away')))
    except (OSError,ValueError,TypeError):return False


def lineup_refresh_requested(root,game,preview):
    """One pregame lineup-derived calculation when both orders become official."""
    path=Path(root)/'cloud_records'/'lineup_refresh_requests'/f"{game.get('id')}.json"
    try:
        req=read_json(path,{}) or {}
        return (bool(preview) and req.get('game_id')==str(game.get('id'))
            and req.get('date')==str(game.get('date'))
            and req.get('kind')=='one_time_confirmed_lineup_refresh'
            and all(str(preview.get(k))==str(game.get(k))
                    for k in ('date','home','away')))
    except (OSError,ValueError,TypeError):return False


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


def store_pregame(game,now,games,root,assets,starter_backfill=None,revision=False,shadows_enabled=False,preliminary=False,preliminary_update=False,lineup_update=False,verified_lineup_history=False):
    id_=str(game['id'])
    original_path=STATE/'predictions'/f'{id_}.json'
    prior_record=read_json(original_path) if original_path.exists() else None
    if lineup_update and (revision or preliminary or preliminary_update):
        raise ValueError('Lineup update must be its own preserved pregame stage')
    if preliminary_update and (revision or preliminary):
        raise ValueError('Preliminary update must be independent of other stages')
    early_path=STATE/'preliminary'/f'{id_}.json'
    early_record=read_json(early_path) if early_path.exists() else None
    if lineup_update:
        if original_path.exists():
            return {'status':'lineup_refresh_final_exists','game_id':id_}
        if not lineup_refresh_requested(root,game,early_record):
            return {'status':'lineup_refresh_unrequested','game_id':id_}
        if not can_preliminary(game,now):
            return {'status':'lineup_refresh_too_late','game_id':id_}
        target_dir=STATE/'lineup_previews'
        if any(target_dir.glob(f'{id_}_*.json')):
            return {'status':'lineup_refresh_already_saved','game_id':id_}
        target=target_dir/f"{id_}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    elif preliminary_update:
        if original_path.exists():
            return {'status':'preliminary_update_final_exists','game_id':id_}
        if not preliminary_update_requested(root,game,early_record):
            return {'status':'preliminary_update_unrequested','game_id':id_}
        if not can_preliminary(game,now):
            return {'status':'preliminary_update_too_late','game_id':id_}
        target_dir=STATE/'preliminary_revisions'
        if any(target_dir.glob(f'{id_}_*.json')):
            return {'status':'preliminary_update_already_saved','game_id':id_}
        target=target_dir/f"{id_}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    elif preliminary:
        target=STATE/'preliminary'/f'{id_}.json'
        if target.exists():
            return {'status':'preliminary_already_frozen','game_id':id_}
        if original_path.exists():
            return {'status':'preliminary_skipped_final_exists','game_id':id_}
        if not can_preliminary(game,now):
            return {'status':'outside_preliminary_window','game_id':id_}
    elif revision:
        if not can_revise(game,now,prior_record):
            return {'status':'revision_not_pregame','game_id':id_}
        revision_dir=STATE/'revisions'
        revision_dir.mkdir(parents=True,exist_ok=True)
        if any(revision_dir.glob(f'{id_}_*.json')):
            return {'status':'already_revised','game_id':id_}
        target=revision_dir/f"{id_}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    else:
        target=original_path
        if target.exists():return {'status':'already_frozen','game_id':id_}
        if not can_forecast(game,now):return {'status':'outside_window','game_id':id_}
    # Use monotonic elapsed time so simulated or offline UTC snapshots remain
    # testable, while a long real network/model call cannot be backdated.
    computation_start=monotonic()
    day=game['date']
    snap=game_evidence(game,now)
    if lineup_update and (not snap or
        not all(snap.get('is_official_lineup',{}).get(side,False) and
                len(snap.get('confirmed_lineups',{}).get(side,[]))==9
                for side in ('home','away'))):
        return {'status':'lineup_refresh_waiting_for_both_official_orders','game_id':id_}
    hitter_history={'status':'not_requested','by_side':{},'prior_pa':{}}
    if verified_lineup_history and snap and any(snap.get('is_official_lineup',{}).values()):
        hitter_history=collect_verified_lineup_history(snap,day)
    clean=clean_game_input(game,verified_pregame=True)
    # Important: future events are filtered from the game history and enriched assets.
    prior=pregame_history_only(games,day)
    prior_assets=historical_cutoff_assets(assets,day)
    result=generate(prior,root,day,clean,assets=prior_assets,n=N_SIMULATIONS,
                    official_snapshot=snap,postseason_context_enabled=True,
                    include_2026_snapshot=True,
                    official_lineup_history=hitter_history.get('by_side'))
    if (preliminary_update or lineup_update) and result['model_version']!=VERSION:
        raise RuntimeError('One-time update returned unexpected model version')
    f=result['forecast'];score=display_forecast(f,game['away'],game['home'],6.5)
    indices=team_indices(games,day,game['away'],game['home'],data_dir=root/'data')
    start=datetime.fromisoformat(game['start_utc'].replace('Z','+00:00'))
    finished_at=now+timedelta(seconds=max(0.,monotonic()-computation_start))
    if finished_at>=start:
        raise RuntimeError('Forecast computation crossed first pitch; refusing to save a pregame record')
    g_type='Postseason' if game.get('game_type')!='R' else 'Regular season'
    status={'data_gaps':result['data_gaps'],
            'starter_pitcher_history':result['provenance']['pitcher_coverage'],
            'lineups_confirmed':{s:len(result['personnel'][s]['lineup'])==9 for s in ('home','away')},
            'pitcher_calibrated':bool((root/'outputs'/'v62_pitcher_calibration.json').exists()),
            'official_snapshot_collected':snap is not None,
            'official_hitter_history':{k:v for k,v in hitter_history.items() if k!='by_side'},
            'starter_backfill':starter_backfill or {'status':'not performed'},
            'run_model_training_years':assets.get('training_years',[]),
            'run_model_training_coverage':assets.get('coverage_note','not reported'),
            'frozen_model_cache':assets.get('model_cache',{}),
            'model_assets_build_seconds':assets.get('build_seconds'),
            'bullpen_workload':matchup_workload(result['personnel'])}
    rec=dict(game_id=id_,date=day,game_type=g_type,home=game['home'],away=game['away'],
        home_name=game['home_name'],away_name=game['away_name'],
        starting_pitchers={'home':game.get('home_pitcher') or 'Not announced',
                           'away':game.get('away_pitcher') or 'Not announced'},
        game_start_utc=start.isoformat(),forecast_created_utc=finished_at.isoformat(),
        minutes_before_game=round((start-finished_at).total_seconds()/60,1),
        model_version=result['model_version'],model_commit=os.getenv('GITHUB_SHA','local'),
        model_training_cutoff=result['provenance']['model_frozen_training'],
        features_cutoff_exclusive=day,
        projected_score={'home':score['home_runs'],'away':score['away_runs'],
                         'sum':score['total'],'exact_probability':float(score['chosen_score_probability'])},
        favorite_aligned_score=f.get('favorite_aligned_score'),
        predicted_home_win=float(f['home_win_probability']),
        elo_home_win=float(result['baseline']['elo_home_win']),
        expected_runs={'home':float(f['home_expected_runs']),'away':float(f['away_expected_runs']),
                       'total':float(f['total_expected_runs'])},
        lineup_evidence=({'captured_utc':snap['captured_utc'],
            'official_source':snap['source'],
            'confirmed_lineups':snap['confirmed_lineups']}
            if snap and any(snap.get('is_official_lineup',{}).values()) else None),
        lineup_adjustment={
            side:{'factor':result['personnel'][side].get('lineup_adjustment',{}).get('factor',1.),
                  'status':result['personnel'][side].get('lineup_adjustment',{}).get('status'),
                  'prior_plate_appearances':result['personnel'][side].get('lineup_adjustment',{}).get('n',0),
                  'history_source':result['personnel'][side].get('lineup_history_source')}
            for side in ('home','away')},
        under_6_5_probability=float(f['under_6_5_probability']),
        total_distribution=f['total_pmf'],
        total_line_probabilities=half_run_line_probabilities(f['total_pmf']),
        score_grid=f['score_grid'],
        modal_exact_scores=f.get('modal_exact_scores',[]),
        projected_score_method='unconditional_simulated_exact_mode',
        team_indices=indices.get('teams',{}),health=status,
        scenario={'postseason_factor':result['adjustments']['postseason_scoring'].get('factor',1.),
                  'starter_weight':result['adjustments']['starter_total_rate']['weight'],
                  'park_factor':result['adjustments']['park']['factor'],
                  'weather_factor':result['adjustments']['weather']['factor']},
        source='Official MLB pregame schedule; baseball-only model; no market inputs',
        forecast_kind=('lineup_confirmed_pregame' if lineup_update else 'preliminary_updated_pregame' if preliminary_update else 'preliminary_pregame' if preliminary else 'revised_pregame' if revision else 'original_pregame'),
        original_forecast_created_utc=(early_record.get('forecast_created_utc') if preliminary_update else prior_record.get('forecast_created_utc') if revision else None),
        revision_reason=('One-time genuinely confirmed nine-player lineups; earlier previews retained'
            if lineup_update else 'One-time V13 model recalibration of frozen preliminary; original retained'
            if preliminary_update else 'Updated verified pitcher history and newer training inputs; original remains immutable'
            if revision else None),
        data_quality='LIMITED' if status['data_gaps'] else 'FEATURES AVAILABLE')
    # A second deadline check covers formatting and payload preparation time.
    final_check=now+timedelta(seconds=max(0.,monotonic()-computation_start))
    if final_check>=start:
        raise RuntimeError('Forecast record would be persisted after first pitch; refusing')
    if (preliminary or preliminary_update or lineup_update) and not can_preliminary(game,final_check):
        raise RuntimeError('Preliminary calculation crossed the early forecast cutoff; refusing')
    rec['forecast_created_utc']=final_check.isoformat()
    rec['minutes_before_game']=round((start-final_check).total_seconds()/60,1)
    if preliminary or preliminary_update or lineup_update:
        # Exclusive create. A second runner cannot silently replace a preview.
        target.parent.mkdir(parents=True,exist_ok=True)
        try:
            with target.open('x',encoding='utf-8') as file:
                json.dump(rec,file,indent=2,sort_keys=True,allow_nan=False)
        except FileExistsError:
            return {'status':'preliminary_already_frozen','game_id':id_}
    else:
        encode_json(target,rec)
    shadow_status={'status':'not_requested'}
    if shadows_enabled and not revision and not preliminary and not preliminary_update and not lineup_update:
        # The primary prediction is ALREADY committed to its frozen JSON.
        # Failure of an experimental challenger can never erase or rewrite it.
        try:
            shadow_status=save_shadow_forecasts(root,game,rec,now,computation_start,
                prior,clean,prior_assets,snapshot=snap,clock=monotonic,n=N_SIMULATIONS,
                lineup_history=hitter_history.get('by_side'))
        except Exception as exc:
            shadow_status={'status':'error','message':str(exc)[:160]}
    return {'status':('lineup_confirmed_saved' if lineup_update else 'preliminary_updated_saved' if preliminary_update else 'preliminary_saved' if preliminary else 'revised_pregame_saved' if revision else 'saved'),'game_id':id_,
            'away':rec['away'],'home':rec['home'],
            'minutes_before_game':rec['minutes_before_game'],
            'shadow_research':shadow_status}


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
    """Score genuine settled originals once; require enough independent dates.

    Duplicate original game IDs fail closed: exclude every copy instead of
    choosing a potentially updated forecast. Legacy originals without a kind
    remain eligible when their identity and pregame timestamps are valid.
    """
    originals={};excluded={}
    def exclude(reason,count=1):excluded[reason]=excluded.get(reason,0)+count
    def valid_metric(value):
        try:
            return (not isinstance(value,bool) and isinstance(value,(int,float))
                    and np.isfinite(float(value)) and value>=0)
        except (OverflowError,TypeError,ValueError):return False
    for rec in records:
        if not isinstance(rec,dict):
            exclude('malformed_record');continue
        if rec.get('forecast_kind') not in ('original_pregame',None):
            exclude('not_original');continue
        gid=rec.get('game_id')
        if isinstance(gid,bool) or not isinstance(gid,(str,int)) or not str(gid).strip():
            exclude('invalid_identity');continue
        originals.setdefault(str(gid).strip(),[]).append(rec)
    evaluated=[]
    for copies in originals.values():
        if len(copies)!=1:
            exclude('duplicate_original',len(copies));continue
        rec=copies[0]
        try:
            day=rec['date']
            if not isinstance(day,str) or date.fromisoformat(day).isoformat()!=day:
                raise ValueError('Invalid official game date')
            if not all(isinstance(rec.get(side),str) and rec[side].strip()
                       for side in ('home','away')) or rec['home']==rec['away']:
                raise ValueError('Invalid teams')
        except (KeyError,TypeError,ValueError):
            exclude('invalid_identity');continue
        if not valid_original(rec):
            exclude('invalid_pregame_timestamp');continue
        evaluation=rec.get('evaluation')
        if not evaluation:continue
        final=rec.get('official_final')
        if (not isinstance(final,dict) or
                any(isinstance(final.get(side),bool) or not isinstance(final.get(side),int)
                    or final[side]<0 for side in ('home','away')) or
                final['home']==final['away']):
            exclude('malformed_final');continue
        fields=('winner_brier','elo_brier','abs_run_error_per_team','under_6_5_brier')
        if (not isinstance(evaluation,dict) or
                not isinstance(evaluation.get('correct_winner'),bool) or
                any(not valid_metric(evaluation.get(key)) for key in fields) or
                any(evaluation[key]>1 for key in ('winner_brier','elo_brier','under_6_5_brier'))):
            exclude('malformed_evaluation');continue
        evaluated.append(rec)
    dates={r['date'] for r in evaluated}
    if not evaluated:
        return {'settled_games':0,'settled_dates':0,'excluded':excluded,
                'status':'Awaiting prospective results'}
    e=[r['evaluation'] for r in evaluated];n=len(e)
    brier=np.array([x['winner_brier'] for x in e]);base=np.array([x['elo_brier'] for x in e]);
    err=np.array([x['abs_run_error_per_team'] for x in e]);
    result=dict(settled_games=n,settled_dates=len(dates),excluded=excluded,
        accuracy=round(float(np.mean([x['correct_winner'] for x in e])),4),
        winner_brier=round(float(brier.mean()),5),elo_brier=round(float(base.mean()),5),
        run_mae_per_team=round(float(err.mean()),3),
        under_6_5_brier=round(float(np.mean([x['under_6_5_brier'] for x in e])),5),
        status=('Insufficient games for uncertainty interval' if n<30 else
                'Insufficient independent dates for uncertainty interval' if len(dates)<10 else
                'Confidence interval available'))
    if n>=30 and len(dates)>=10:
        delta=base-brier
        # Grouped resampling by game DATE, not individual bets; avoid fake precision.
        bydate={}
        for r in evaluated:bydate.setdefault(r['date'],[]).append(r['evaluation']['elo_brier']-r['evaluation']['winner_brier'])
        d=sorted(bydate);rng=np.random.default_rng(2026)
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
    originals=[]
    for f in (STATE/'predictions').glob('*.json'):
        try:
            rec=read_json(f)
            # Frozen originals have exactly one canonical file per MLB game.
            # Ignore misplaced copies before any report can count them twice.
            if isinstance(rec,dict) and str(rec.get('game_id'))==f.stem:
                originals.append(rec)
        except (OSError,ValueError,TypeError):pass
    attach_shadows(originals,root)
    by_id={str(x.get('game_id')):x for x in originals}
    preliminary_records=[]
    for f in sorted((root/'cloud_records'/'preliminary').glob('*.json')):
        try:
            early=read_json(f)
            gid=str(early.get('game_id'))
            if (early.get('forecast_kind')!='preliminary_pregame'
                    or gid!=f.stem or not early.get('game_start_utc')):
                continue
            from cloud.v8_evaluate import valid_original,timestamp
            if not valid_original(early):
                continue
            matched=by_id.get(gid)
            if matched and all(str(matched.get(k))==str(early.get(k))
                               for k in ('game_id','date','home','away','game_start_utc')):
                if timestamp(early['forecast_created_utc']) < timestamp(matched['forecast_created_utc']):
                    matched['preliminary_comparison']={
                        'score':early.get('projected_score'),
                        'expected_runs':early.get('expected_runs'),
                        'predicted_home_win':early.get('predicted_home_win'),
                        'model_version':early.get('model_version'),
                        'forecast_created_utc':early.get('forecast_created_utc')}
                if matched.get('official_final'):
                    early['official_final']=matched['official_final']
            preliminary_records.append(early)
        except (OSError,ValueError,KeyError,TypeError):
            continue
    for f in sorted((root/'cloud_records'/'preliminary_revisions').glob('*.json')):
        try:
            upd=read_json(f)
            ident=str(upd.get('game_id'))
            if (upd.get('forecast_kind')!='preliminary_updated_pregame'
                    or not f.name.startswith(ident+'_')):
                continue
            original_early=next((e for e in preliminary_records
                if str(e.get('game_id'))==ident),None)
            if not original_early:continue
            from cloud.v8_evaluate import valid_original,timestamp
            if (not valid_original(upd) or
                any(str(upd.get(k))!=str(original_early.get(k))
                    for k in ('game_id','date','home','away','game_start_utc')) or
                timestamp(upd['forecast_created_utc'])<=timestamp(original_early['forecast_created_utc'])):
                continue
            final=by_id.get(ident)
            if final and final.get('official_final'):
                upd['official_final']=final['official_final']
            upd['preliminary_comparison']={'score':original_early.get('projected_score'),
                'expected_runs':original_early.get('expected_runs'),
                'predicted_home_win':original_early.get('predicted_home_win'),
                'model_version':original_early.get('model_version'),
                'forecast_created_utc':original_early.get('forecast_created_utc')}
            preliminary_records.append(upd)
        except (OSError,KeyError,ValueError,TypeError):
            continue
    for file in sorted((root/'cloud_records'/'lineup_previews').glob('*.json')):
        try:
            lineup_record=read_json(file)
            ident=str(lineup_record.get('game_id'))
            if (lineup_record.get('forecast_kind')!='lineup_confirmed_pregame'
                    or not file.name.startswith(ident+'_')):
                continue
            from cloud.v8_evaluate import valid_original,timestamp
            early=next((e for e in preliminary_records
                        if str(e.get('game_id'))==ident
                        and e.get('forecast_kind')=='preliminary_pregame'),None)
            if not early or not valid_original(lineup_record):
                continue
            if any(str(lineup_record.get(k))!=str(early.get(k))
                   for k in ('game_id','date','home','away','game_start_utc')):
                continue
            if timestamp(lineup_record['forecast_created_utc'])<=timestamp(early['forecast_created_utc']):
                continue
            evidence=lineup_record.get('lineup_evidence') or {}
            if any(len(evidence.get('confirmed_lineups',{}).get(side,[]))!=9
                   for side in ('home','away')):
                continue
            matched=by_id.get(ident)
            if matched and matched.get('official_final'):
                lineup_record['official_final']=matched['official_final']
            previous=next((e for e in reversed(preliminary_records)
                if str(e.get('game_id'))==ident),early)
            lineup_record['preliminary_comparison']={
                'score':previous.get('projected_score'),
                'expected_runs':previous.get('expected_runs'),
                'predicted_home_win':previous.get('predicted_home_win'),
                'model_version':previous.get('model_version'),
                'forecast_created_utc':previous.get('forecast_created_utc')}
            preliminary_records.append(lineup_record)
        except (OSError,TypeError,ValueError,KeyError):
            continue
    revisions=[]
    for f in (STATE/'revisions').glob('*.json'):
        try:
            r=read_json(f)
            initial=by_id.get(str(r.get('game_id')))
            if not initial:continue
            r['original_comparison']={
                'score':initial.get('projected_score'),
                'expected_runs':initial.get('expected_runs'),
                'predicted_home_win':initial.get('predicted_home_win'),
                'starter_pitcher_history':initial.get('health',{}).get('starter_pitcher_history',{}),
                'run_model_training_coverage':initial.get('health',{}).get('run_model_training_coverage','not reported')}
            if initial.get('official_final'):
                r['official_final']=initial['official_final']
            revisions.append(r)
        except (ValueError,TypeError):pass
    entries=originals+revisions+preliminary_records
    # Within each matchup always show the final/explicit revision ahead of
    # the preliminary, while allowing both snapshots in the selector.
    priority={'preliminary_pregame':0,'preliminary_updated_pregame':1,'lineup_confirmed_pregame':2,'original_pregame':3,'revised_pregame':4}
    entries.sort(key=lambda r:(r.get('game_start_utc',''),
                   priority.get(r.get('forecast_kind'),1),
                   r.get('forecast_created_utc','')),reverse=True)
    # Start an independent capture-rate denominator on the day this monitor launches.
    # Historic 2026 playoff replays are NOT retroactively called missed forecasts.
    capture=prospective_capture_report(root,now.astimezone(ET).date())
    audit_path=root/'cloud_records'/'official_schedule_audit_latest.json'
    if audit_path.exists():
        try:
            official_audit=read_json(audit_path)
        except (OSError,ValueError,TypeError):
            official_audit={'status':'unreadable'}
    else:
        official_audit={'status':'not_yet_run'}
    if (official_audit.get('as_of_exclusive_et_date') not in
            (None,now.astimezone(ET).date().isoformat())):
        official_audit={**official_audit,'last_status':official_audit.get('status'),
                        'status':'stale'}
    output={'updated_utc':now.isoformat(),
        'local_timezone':'America/New_York',
        'prospective_capture':capture,
        'official_schedule_audit':official_audit,
        'predictions':entries[:350],
        'prospective_performance':prospective_metrics(originals),
        'full_distribution_validation':evaluate_full_distribution(originals),
        'model_health':prospective_health_report(root),
        'shadow_comparisons':challenger_metrics(originals),
        'two_stage_comparison':paired_stage_metrics(root),
        'operations':summary,
        'disclaimer':'Baseball-only research forecast. Past outcome never enters a pregame prediction. Unverified advanced inputs are marked missing.'}
    site=root/'site';site.mkdir(exist_ok=True,parents=True)
    encode_json(site/'data.json',output)
    encode_json(root/'cloud_records'/'coverage_latest.json',capture)
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
        # Independently fetch recent official finals; an import outage must not
        # make the imported-only capture denominator appear complete.
        try:
            audit=official_schedule_reconciliation(root,today)
        except Exception as exc:
            audit={'status':'unavailable','as_of_exclusive_et_date':today.isoformat(),
                   'error':str(exc)[:170]}
            summary['events'].append(f'Independent schedule audit unavailable: {str(exc)[:170]}')
        encode_json(root/'cloud_records'/'official_schedule_audit_latest.json',audit)
        summary['official_schedule_audit_status']=audit['status']
        try:
            summary['pitching_import_status']=initialize_details(root,now)
        except Exception as exc:summary['events'].append(f'Historical pitcher import unavailable: {str(exc)[:160]}')
        try:
            summary['recent_boxscores']=refresh_recent_boxscores(root,today)
        except Exception as exc:summary['events'].append(f'Recent boxscores unavailable: {str(exc)[:160]}')
    games=None;assets=None
    candidate_games=[]
    if network:
        for dt in official_schedule_days(now):
            if dt.year<2026:continue
            try:candidate_games+=fetch_schedule(dt)
            except Exception as exc:summary['events'].append(f'Schedule unavailable for {dt}: {str(exc)[:130]}')
    seen_ids=set()
    upcoming=[]
    for match in candidate_games:
        gid=str(match.get('id') or '')
        if gid in seen_ids:continue
        seen_ids.add(gid)
        original=STATE/'predictions'/f'{gid}.json'
        preview=STATE/'preliminary'/f'{gid}.json'
        has_lineup_update=any((STATE/'lineup_previews').glob(f'{gid}_*.json'))
        wants_lineup_update=(not original.exists() and preview.exists()
            and not has_lineup_update
            and lineup_refresh_requested(root,match,read_json(preview))
            and can_preliminary(match,now))
        has_preliminary_update=any((STATE/'preliminary_revisions').glob(f'{gid}_*.json'))
        wants_preliminary_update=(not original.exists() and preview.exists()
            and not has_preliminary_update
            and preliminary_update_requested(root,match,read_json(preview))
            and can_preliminary(match,now))
        wants_revision=(original.exists() and revision_requested(root,match) and
            not any((STATE/'revisions').glob(f'{gid}_*.json')) and
            can_revise(match,now,read_json(original)))
        if wants_revision:
            upcoming.append({**match,'_revision':True})
        elif not original.exists() and can_forecast(match,now):
            upcoming.append(match)
        elif not original.exists() and not preview.exists() and can_preliminary(match,now):
            upcoming.append({**match,'_preliminary':True})
        elif wants_preliminary_update:
            upcoming.append({**match,'_preliminary_update':True})
        elif wants_lineup_update:
            upcoming.append({**match,'_lineup_update':True})
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
                summary['model_assets_build_seconds']=assets.get('build_seconds')
                summary['frozen_model_cache']=assets.get('model_cache')
            summary['events'].append(store_pregame(
                match,utcnow() if network else now,games,root,assets,
                starter_backfill=backfills.get(str(match['id'])),
                revision=bool(match.get('_revision')),
                shadows_enabled=not bool(match.get('_preliminary') or match.get('_preliminary_update') or match.get('_lineup_update')),
                preliminary=bool(match.get('_preliminary')),
                preliminary_update=bool(match.get('_preliminary_update')),
                lineup_update=bool(match.get('_lineup_update')),
                verified_lineup_history=bool(network)))
        except Exception as exc:
            summary['events'].append({'status':'forecast_failed','game_id':match['id'],
                                      'error':str(exc)[:180]})
    summary['new_settlements']=settle(root)
    summary['status']='finished'
    if network and not fast and 'refreshed_finished_games' in summary:
        # This file is independent of last_run.json because short pregame jobs
        # overwrite last_run while intentionally skipping official result imports.
        stamp=utcnow() if network else now
        encode_json(STATE/'daily_maintenance.json',{
            'successful_refresh_utc':stamp.isoformat(),
            'as_of_exclusive_et_date':today.isoformat(),
            'official_games_imported':summary['refreshed_finished_games'],
            'new_settlements':summary['new_settlements'],
            'status':'complete'})
        summary['daily_maintenance']='complete'
    elif not fast:
        summary['daily_maintenance']='incomplete (official results import unavailable)'
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

