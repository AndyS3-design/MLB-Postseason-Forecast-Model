"""Prospective forecast-coverage audit using only imported OFFICIAL final games.

Starts at the independent-monitoring launch date, avoiding past replay games
counted as genuine prospective forecast misses. The denominator is *only*
completed games already imported by the pipeline, not all MLB schedule games.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
from cloud.refresh import all_finals
from cloud.v8_evaluate import valid_original,timestamp

TRACKING_START=date(2026,10,14)
DEFAULT_MISSING_LIMIT=12

def load_originals(root):
    path=Path(root)/'cloud_records/predictions'
    records={}
    bad=[]
    for f in sorted(path.glob('*.json')):
        try:
            r=json.loads(f.read_text(encoding='utf-8'))
            key=str(r['game_id'])
            if key in records or key!=f.stem:
                bad.append(f.name)
                continue
            records[key]=r
        except (OSError,ValueError,TypeError,KeyError):
            bad.append(f.name)
    return records,bad

def _date(d):
    return date.fromisoformat(str(d)[:10])

def _identity_match(original,final):
    return (str(original.get('game_id'))==str(final.get('game_id'))
            and str(original.get('date'))==str(final.get('date'))
            and str(original.get('home'))==str(final.get('home'))
            and str(original.get('away'))==str(final.get('away')))

def _stage(g):
    return 'regular_season' if g.get('game_type')=='R' else 'postseason'

def summarize(root,as_of,tracking_start=TRACKING_START):
    """Measure captured vs missing among already-imported completed games.

    A confirmed official final must be STRICTLY before the ET as_of date.
    Thus games in progress today cannot be counted, settled, or judged missing.
    """
    root=Path(root)
    as_of=_date(as_of)
    tracking_start=_date(tracking_start)
    records,bad_files=load_originals(root)
    finals=all_finals(root)
    eligible=[g for g in finals.values()
        if g.get('game_id') and tracking_start<=_date(g['date'])<as_of]
    eligible.sort(key=lambda g:(g['date'],str(g['game_id'])))
    found=set()
    correct=[]
    missed=[]
    identity_errors=[]
    rejected_late=[]
    awaiting_settlement=[]
    periods=defaultdict(lambda:dict(completed=0,captured=0,missing=0))
    for g in eligible:
        game_id=str(g['game_id'])
        period=g['date'][:7]+'/'+_stage(g)
        periods[period]['completed']+=1
        record=records.get(game_id)
        if record and not _identity_match(record,g):
            identity_errors.append({'game_id':game_id,'date':g['date'],'issue':'identity conflict'})
            periods[period]['missing']+=1
            continue
        if record is None:
            missed.append({'game_id':game_id,'date':g['date'],
                'away':g['away'],'home':g['home'],
                'reason':'No saved original before first pitch'})
            periods[period]['missing']+=1
            continue
        if not valid_original(record):
            rejected_late.append({'game_id':game_id,'date':g['date'],
                'reason':'Existing record is not a valid pre-first-pitch original'})
            periods[period]['missing']+=1
            continue
        correct.append(record)
        found.add(game_id)
        periods[period]['captured']+=1
        if not record.get('official_final'):
            awaiting_settlement.append(game_id)
        else:
            f=record['official_final']
            if (int(f['home'])!=int(g['home_final'])
                    or int(f['away'])!=int(g['away_final'])):
                identity_errors.append({'game_id':game_id,'date':g['date'],
                    'issue':'Official final differs from settled score'})
    valid_prior=[r for r in records.values()
        if valid_original(r) and tracking_start<=_date(r['date'])<as_of]
    prior_no_final=[str(r['game_id']) for r in valid_prior
        if str(r.get('game_id')) not in finals]
    timely=sum(8 <= (timestamp(r['game_start_utc'])-
        timestamp(r['forecast_created_utc'])).total_seconds()/60<=30
        for r in correct)
    shadows=sum(bool((root/'cloud_records/challengers'/f"{r['game_id']}.json").exists())
        for r in correct)
    n=len(eligible)
    report={'status':'waiting_for_completed_games' if n==0 else 'tracking_imported_finals',
        'tracking_start_date':tracking_start.isoformat(),
        'as_of_exclusive_et_date':as_of.isoformat(),
        'scope':'Only official completed MLB games already imported by the cloud service',
        'completed_imported_games':n,
        'games_with_valid_original_pregame_forecast':len(correct),
        'games_without_valid_original':n-len(correct),
        'capture_fraction':round(len(correct)/n,4) if n else None,
        'captured_within_8_to_30_min_window':timely,
        'capture_window_fraction':round(timely/len(correct),4) if correct else None,
        'settled_original_forecasts':sum(bool(r.get('official_final')) for r in correct),
        'originals_awaiting_settlement':len(awaiting_settlement),
        'paired_shadow_files_for_captured_games':shadows,
        'originals_without_imported_final':len(prior_no_final),
        'unreadable_original_files':bad_files[:DEFAULT_MISSING_LIMIT],
        'identity_or_result_conflicts':identity_errors[:DEFAULT_MISSING_LIMIT],
        'missing_originals':missed[:DEFAULT_MISSING_LIMIT],
        'late_or_invalid_originals':rejected_late[:DEFAULT_MISSING_LIMIT],
        'captured_pending_settlement_ids':awaiting_settlement[:DEFAULT_MISSING_LIMIT],
        'periods':dict(sorted(periods.items())),
        'notes':[
          'This metric is not prediction accuracy. It measures the capture rate among imported official final games.',
          'Missing game predictions are counted only after the official final enters local data.',
          'Historical games before monitoring launch are excluded from this prospective capture rate.',
          'GitHub scheduled jobs are best effort; missed windows must not be backdated.',
          'Shadow records never count as additional original forecasts.']}
    return report
