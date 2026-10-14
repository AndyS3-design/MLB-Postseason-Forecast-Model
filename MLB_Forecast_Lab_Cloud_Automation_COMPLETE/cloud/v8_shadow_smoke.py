"""End-to-end REAL estimator smoke for variant API; historical RESEARCH ONLY.

This never writes to cloud_records and is NOT a prospective pregame prediction.
No actual final score, verified starter or lineup from the old game is an input.
"""
import json,time
from pathlib import Path
from extended_eval import all_games
from v4_workflow import generate,build_assets
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only

def main():
    root=Path(__file__).resolve().parents[1]
    start=time.monotonic()
    games=all_games(root/'data',True)
    assets=build_assets(games,root)
    day='2026-10-11'
    prior=pregame_history_only(games,day)
    assert all(str(x['date'])[:10]<day for x in prior)
    match=clean_game_input({'id':'smoke-20261011-LAN-MIL','date':day,
          'away':'LAN','home':'MIL','game_type':'L'},
          verified_pregame=False)
    fit=historical_cutoff_assets(assets,day)
    kwargs=dict(assets=fit,official_snapshot=None,n=1600)
    variants={
      'primary':{},
      'without_extra_starter_correction':{'starter_correction_override':0.},
      'without_postseason_context':{'postseason_context_enabled':False,
          'include_2026_snapshot':False}
    }
    report={'status':'RETROSPECTIVE SOFTWARE SMOKE ONLY — NOT PRE-GAME EVIDENCE',
         'matchup':'LAN @ MIL','date':day,'historical_cutoff_exclusive':day,
         'training_years':assets['training_years'],'variants':{}}
    for label,settings in variants.items():
        model=generate(prior,root,day,match,**kwargs,**settings)
        f=model['forecast'];w=float(f['home_win_probability'])
        t=float(f['total_expected_runs'])
        assert 0<=w<=1 and 0<=f['under_6_5_probability']<=1 and 1<t<30
        report['variants'][label]={
           'home_win_probability':w,
           'total_expected_runs':t,
           'under_6_5_probability':float(f['under_6_5_probability']),
           'additional_starter_weight':float(model['adjustments']['starter_total_rate']['weight']),
           'postseason_run_factor':float(model['adjustments']['postseason_scoring']['factor'])}
        print(label,'home',round(w,4),'total',round(t,4),flush=True)
    a=report['variants']
    assert a['primary']['postseason_run_factor']<1
    assert a['without_postseason_context']['postseason_run_factor']==1
    assert a['without_extra_starter_correction']['additional_starter_weight']==0
    assert a['primary']['additional_starter_weight']>=0
    report['runtime_seconds']=round(time.monotonic()-start,2)
    out=root/'outputs/v8_validation/shadow_variant_real_model_smoke.json'
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps(report,indent=2))
    print('SMOKE PASSED',out,flush=True)
if __name__=='__main__':main()
