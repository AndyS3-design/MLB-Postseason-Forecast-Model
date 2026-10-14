"""Never-overwrite experimental pregame forecasts for prospective comparisons.

These extra probabilistic models are SHADOW research variants: they do not
alter published primary predictions. All variants use the same pregame
snapshot, history cutoff, frozen training assets, and game identity.
"""
from __future__ import annotations
from datetime import datetime,timedelta
from pathlib import Path
import json,math
from time import monotonic
from typing import Callable
from v4_workflow import generate

def variants(game_type):
    result=[('without_extra_starter_correction',
             {'starter_correction_override':0.0},
             'Original scoring model with no additional calibrated starter correction')]
    if str(game_type)!='R':
        result.append(('without_postseason_context',
                       {'postseason_context_enabled':False,'include_2026_snapshot':False},
                       'Regular-season run rate with no postseason overlay'))
    return result

def _timestamp(x):
    return datetime.fromisoformat(str(x).replace('Z','+00:00'))

def evaluate_pair(originals):
    """Paired scoring on exactly the same truly prospective settled games."""
    names=set()
    for r in originals:
        names.update((r.get('shadow_forecasts') or {}).keys())
    report={}
    for name in sorted(names):
        included=[r for r in originals if r.get('official_final')
                  and (r.get('shadow_forecasts') or {}).get(name,{}).get('status')=='saved']
        if not included:
            report[name]={'n':0,'status':'Awaiting new completed games'}
            continue
        sums={'winner_brier_main':0.,'winner_brier_challenger':0.,
              'total_mae_main':0.,'total_mae_challenger':0.,
              'under_6_5_brier_main':0.,'under_6_5_brier_challenger':0.}
        for r in included:
            final=r['official_final'];y=float(final['home']>final['away'])
            total=final['home']+final['away'];under=float(total<=6)
            variant=r['shadow_forecasts'][name]
            sums['winner_brier_main']+=(r['predicted_home_win']-y)**2
            sums['winner_brier_challenger']+=(variant['home_win_probability']-y)**2
            sums['total_mae_main']+=abs(r['expected_runs']['total']-total)
            sums['total_mae_challenger']+=abs(variant['total_expected_runs']-total)
            sums['under_6_5_brier_main']+=(r['under_6_5_probability']-under)**2
            sums['under_6_5_brier_challenger']+=(variant['under_6_5_probability']-under)**2
        report[name]={'n':len(included),'status':'small sample; exploratory' if len(included)<30 else 'prospective paired comparison',
                      **{key:round(value/len(included),5) for key,value in sums.items()}}
    return report

def save_shadow_forecasts(root,game,original,now,started_monotonic,prior,clean,assets,
                          snapshot=None,generator:Callable=generate,clock=monotonic,
                          n=12000,min_time_left=75):
    """Create a separate immutable record if ALL comparisons finish before first pitch.

    Primary original forecast is saved before invoking this function. A failure
    or slow challenger cannot delete or alter the original forecast.
    """
    root=Path(root)
    path=root/'cloud_records'/'challengers'/f"{game.get('id')}.json"
    if path.exists():return {'status':'already_frozen'}
    try:
        start=_timestamp(game['start_utc'])
        frozen=_timestamp(original['forecast_created_utc'])
    except (KeyError,ValueError,TypeError):
        return {'status':'invalid_timing'}
    if str(original.get('game_id'))!=str(game.get('id')) or original.get('date')!=game.get('date'):
        return {'status':'identity_mismatch'}
    if str(original.get('home'))!=str(game.get('home')) or str(original.get('away'))!=str(game.get('away')):
        return {'status':'identity_mismatch'}
    if frozen>=start:return {'status':'not_original_pregame'}
    if n<1000:return {'status':'invalid_simulation_size'}
    def now_at_completion():
        return now+timedelta(seconds=max(0.,clock()-started_monotonic))
    forecast={}
    for name,kwargs,description in variants(game.get('game_type','R')):
        if (start-now_at_completion()).total_seconds()<min_time_left:
            return {'status':'insufficient_pregame_window','finished_variants':len(forecast)}
        try:
            result=generator(prior,root,game['date'],clean,assets=assets,n=n,
                             official_snapshot=snapshot,**kwargs)
            f=result['forecast']
            values={'home_win_probability':float(f['home_win_probability']),
                    'total_expected_runs':float(f['total_expected_runs']),
                    'under_6_5_probability':float(f['under_6_5_probability'])}
            if not all(math.isfinite(v) for v in values.values()):
                raise ValueError('Non-finite shadow forecast')
            if not 0<=values['home_win_probability']<=1 or not 0<=values['under_6_5_probability']<=1:
                raise ValueError('Invalid shadow probability')
            if values['total_expected_runs']<=0 or values['total_expected_runs']>30:
                raise ValueError('Invalid shadow expected runs')
            forecast[name]={'status':'saved','description':description,**values}
        except Exception as exc:
            return {'status':'shadow_failed','reason':str(exc)[:140],'variant':name}
    stamp=now_at_completion()
    if stamp>=start:return {'status':'late_shadow_rejected'}
    payload={'game_id':str(game['id']),'date':game['date'],'home':game['home'],'away':game['away'],
             'game_start_utc':start.isoformat(),'original_forecast_created_utc':frozen.isoformat(),
             'shadow_created_utc':stamp.isoformat(),
             'features_cutoff_exclusive':game['date'],
             'model_version':original.get('model_version'),'simulations_per_variant':n,
             'variants':forecast,
             'source':'Same original pregame inputs and official snapshot; baseball-only; RESEARCH ONLY',
             'limitations':'Do not select winning challenger retrospectively on the games used to compare them.'}
    path.parent.mkdir(parents=True,exist_ok=True)
    # Create-exclusive: a retry can never overwrite another pregame snapshot.
    with path.open('x',encoding='utf-8') as f:
        json.dump(payload,f,indent=2,sort_keys=True,allow_nan=False)
    return {'status':'shadows_saved','n_variants':len(forecast),'path':str(path)}

def attach_shadows(originals,root):
    for r in originals:
        path=Path(root)/'cloud_records/challengers'/f"{r.get('game_id')}.json"
        if not path.is_file():continue
        try:
            payload=json.loads(path.read_text())
            if (str(payload.get('game_id'))!=str(r.get('game_id'))
                or payload.get('date')!=r.get('date')
                or payload.get('home')!=r.get('home') or payload.get('away')!=r.get('away')):
                continue
            if _timestamp(payload['shadow_created_utc'])>=_timestamp(r['game_start_utc']):
                continue
            if _timestamp(payload['original_forecast_created_utc'])!=_timestamp(r['forecast_created_utc']):
                continue
            r['shadow_forecasts']=payload.get('variants',{})
            r['shadow_created_utc']=payload.get('shadow_created_utc')
        except (KeyError,ValueError,TypeError,OSError,json.JSONDecodeError):
            continue
