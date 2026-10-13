"""V6.2: transparent, past-only starter-rate correction.

The legacy inning simulator normalized each pitcher's effects away when it
constructed TOTAL expected runs. This module makes the effect on the total
explicit, while guarding against double counting the starter already present
in the trained conditional Poisson run model.

This is an experimental research correction, selected exclusively using 2024
regular-season validation. The 2025 season remains a diagnostic holdout.
"""
from __future__ import annotations
import math
from pathlib import Path
import json
import numpy as np
import pandas as pd

ERA_REFERENCE=4.35
STARTER_FEATURE_NEUTRAL={
    'opp_sp_era':4.3, 'opp_sp_kbb':2.0, 'opp_sp_innings':5.0,
    'opp_sp_known':0.0, 'opp_sp_rest':6.0,
}
CANDIDATES=(0.0,0.25,0.5,0.75,1.0)


def neutralize_starters(frame):
    """Force ONLY opponent-starter columns to the no-history prior.

    Keep each team's offense, team run prevention, bullpen, Elo, park, etc.
    unchanged. Works with time-locked feature rows, not final game scores.
    """
    clean=frame.copy()
    for key,value in STARTER_FEATURE_NEUTRAL.items():
        if key in clean.columns:clean[key]=value
    return clean


def starter_total_factor(era,innings,known):
    """Fractional change in an opponent's 9-inning run expectation.

    The weighted ERA comes from recorded PRIOR starts, shrunk by the upstream
    data builder. This is NOT an unsupported unconditional 'aces go under' rule.
    Returns 1.0 when insufficient history exists.
    """
    try:
        era=float(era);ip=float(innings);n=int(known)
    except (TypeError,ValueError,OverflowError):return 1.0
    if not all(math.isfinite(z) for z in (era,ip)) or n<3 or era<=0:return 1.0
    ip=max(2.5,min(7.5,ip))
    # Reliability declines for small pitcher samples; starter only covers part
    # of the game. Remaining innings are handled by the team bullpen model.
    share=(ip/9.0)*(n/(n+3.0))
    relative=max(.40,min(1.85,era/ERA_REFERENCE))
    return max(.64,min(1.42,1.0+share*(relative-1.0)))


def blended_rates(fit,rows,strength):
    """Blend conditioned learned rates with neutral-rate plus pitcher physics.

    At strength=0, returns EXACTLY the existing learned conditional model.
    At strength=1, a neutral-starter base is multiplied by a starter's
    reliability/shrunk-ERA and expected-innings correction.
    """
    strength=float(strength)
    if not math.isfinite(strength) or not 0<=strength<=1:
        raise ValueError('Pitcher correction weight must be from 0 to 1')
    X=rows[fit.features].to_numpy(dtype=float)
    conditioned=np.clip(np.asarray(fit.pipeline.predict(X),dtype=float),.3,16.)
    # Compute the neutral-starter counterfactual even when the calibrated
    # extra correction is disabled. This is for honest, transparent auditing:
    # the base V4 model can still depend on starter features when strength=0.
    neutral=neutralize_starters(rows)
    reference=np.clip(np.asarray(fit.pipeline.predict(neutral[fit.features].to_numpy(dtype=float)),dtype=float),.3,16.)
    if strength==0:
        return conditioned,conditioned.copy(),reference,np.ones(len(rows))
    factors=np.array([starter_total_factor(era,ip,known) for era,ip,known in zip(
        rows['opp_sp_era'],rows['opp_sp_innings'],rows['opp_sp_known'])],dtype=float)
    # Without a usable starter sample, the original prediction is retained.
    effective=np.where(rows['opp_sp_known'].to_numpy(dtype=float)>=3,
      (1-strength)*conditioned + strength*(reference*factors), conditioned)
    effective=np.clip(effective,.3,16.)
    return effective,conditioned,reference,factors


def _score(y,p):
    y=np.asarray(y,dtype=float);p=np.clip(np.asarray(p,dtype=float),.3,16.)
    return {'mae':float(np.mean(np.abs(y-p))),
            'mean_poisson_log_loss_omitting_factorial':float(np.mean(p-y*np.log(p)))}


def calibrate_from_rows(frame):
    """Choose starter weight on 2024 ONLY, then inspect 2025 untouched.

    Fits training model to 2023; 2024 determines weight; then refits to
    2023-24 (retaining selected model regularization) for 2025 diagnostics.
    This does not prove financial value or an isolated pitcher causal effect.
    """
    from sklearn.linear_model import PoissonRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from v4_matchup_core import train_frozen_run_model
    frozen=train_frozen_run_model(frame)
    features=frozen.features
    alpha=frozen.alpha
    # Use existing frozen V4 features (but never the current game's outcome).
    eligible=frame[(frame['game_type']=='R')&(frame['year'].isin([2023,2024,2025]))].copy()
    subsets={yr:eligible[eligible.year==yr] for yr in (2023,2024,2025)}
    if len(subsets[2023])<3500 or len(subsets[2024])<3500 or len(subsets[2025])<3500:
        raise ValueError('Need all three regular seasons for 2024 selection and 2025 evaluation')
    class Fit:
        def __init__(self,src):
            self.features=features
            self.pipeline=make_pipeline(StandardScaler(),PoissonRegressor(alpha=alpha,max_iter=300))
            self.pipeline.fit(src[features].to_numpy(dtype=float),src['runs_actual'].to_numpy(dtype=float))
    fit23=Fit(subsets[2023]);val=subsets[2024];yv=val['runs_actual'].to_numpy(dtype=float)
    coverage_2024=int((val['opp_sp_known']>=3).sum())
    if coverage_2024<500:
        raise ValueError(f'Only {coverage_2024} of the 2024 team-game rows have 3+ prior detailed starts; import Retrosheet detailed pitching data')
    validation=[]
    for strength in CANDIDATES:
        p,*_=blended_rates(fit23,val,strength)
        validation.append({'weight':strength,**_score(yv,p)})
    best=min(validation,key=lambda r:(r['mean_poisson_log_loss_omitting_factorial'],r['weight']))
    refit=Fit(eligible[eligible.year.isin([2023,2024])]);test=subsets[2025];yt=test['runs_actual'].to_numpy(dtype=float)
    p_legacy,*_=blended_rates(refit,test,0)
    p_selected,*_=blended_rates(refit,test,best['weight'])
    return {
      'version':'6.2-starter-rate-2024-selected',
      'selected_weight':float(best['weight']),
      'reference_era':ERA_REFERENCE,'run_model_alpha':alpha,'run_model_features':features,
      'tuning_season':2024,'training_season':2023,'diagnostic_holdout_season':2025,
      'observed_starter_coverage_2024':coverage_2024,
      'observed_starter_coverage_2025':int((test['opp_sp_known']>=3).sum()),
      'validation_2024':validation,
      'holdout_2025':{'n_games':len(test)//2,'legacy':_score(yt,p_legacy),
                      'selected':_score(yt,p_selected)},
      'notes':['No 2025/2026 result was used to select the pitcher correction weight.',
       'Smoothed ERA and innings projections were available before each historical game.',
       'Results reflect retrospective development; fresh prospective tests remain necessary.',
       'Regular-season run error does not establish a postseason or betting advantage.']}


def read_calibration(path):
    path=Path(path)
    if not path.is_file():return None
    obj=json.loads(path.read_text(encoding='utf-8'))
    if obj.get('version')!='6.2-starter-rate-2024-selected':raise ValueError('Unknown pitcher calibration version')
    weight=float(obj.get('selected_weight'))
    if weight not in CANDIDATES:raise ValueError('Pitcher weight must be one of the validated candidates')
    if int(obj.get('observed_starter_coverage_2024',0))<500:raise ValueError('Too little validation starter history')
    return obj


def apply_to_base(base,fit,weight):
    """Return starter-adjusted game-day μ and clear audit for each offense."""
    rows=pd.DataFrame([base['home_features'],base['away_features']])
    output,conditioned,neutral,factors=blended_rates(fit,rows,weight)
    report={}
    for i,side in enumerate(('home','away')):
        r=rows.iloc[i]
        report[side]=dict(
          previously_learned_rate=round(float(conditioned[i]),3),
          neutral_starter_rate=round(float(neutral[i]),3),
          starter_total_factor=round(float(factors[i]),4),
          adjusted_rate=round(float(output[i]),3),
          prior_starts_with_details=int(r['opp_sp_known']),
          prior_smoothed_era=round(float(r['opp_sp_era']),3),
          projected_opposing_starter_ip=round(float(r['opp_sp_innings']),2),
          starter_applied=bool(weight>0 and r['opp_sp_known']>=3))
    return float(output[0]),float(output[1]),report
