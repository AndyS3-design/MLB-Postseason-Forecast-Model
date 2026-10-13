"""2025/2026 retrospective out-of-year run-model diagnostics.

The run model is tuned on 2024 only, trained on 2023–24. Holdouts 2025 and
2026 have already influenced past model development; do NOT call pristine tests.
"""
from __future__ import annotations
import argparse,json
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import skellam
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games
from v4_matchup_core import historical_team_rows,train_frozen_run_model,predict_rates
from v4_defense import add_fielding_errors
from backtest import read_rows, make_features, preds
from forecast_engine import build_run_fit


def paired_bootstrap(data,comparison='mae',reps=700,seed=1008):
    if not data:return None
    byday={}
    for x in data:byday.setdefault(x['date'],[]).append(x['delta'])
    values=list(byday.values());n=len(values)
    if n<15:return None
    sums=np.array([sum(v) for v in values]);counts=np.array([len(v) for v in values]);rng=np.random.default_rng(seed)
    ids=rng.integers(0,n,size=(reps,n))
    means=sums[ids].sum(axis=1)/counts[ids].sum(axis=1)
    return [float(v) for v in np.percentile(means,[2.5,97.5])]


def report(fit,allrows,year,kind='R'):
    subset=allrows[(allrows.year==year)&(allrows.game_type==kind)].copy()
    if subset.empty:return {'status':'not available','games':0}
    p=np.asarray(predict_rates(fit,subset));y=subset.runs_actual.to_numpy(dtype=float)
    baseline=np.full_like(y,4.5)
    absnew=np.abs(y-p);absbase=np.abs(y-baseline)
    bad=lambda x:float(np.mean(x))
    pairs=[{'date':str(day),'delta':float(b-a)} for day,a,b in zip(subset.date,absnew,absbase)]
    # Group home/away by same game; individual run expectations imply a single unadjusted
    # probability. This winner proxy does NOT test the inning simulation engine itself.
    predrows=subset[['game_id','date','side','team','opponent','runs_actual']].copy()
    predrows['mu']=p
    win=[]
    for gid,g in predrows.groupby('game_id',sort=False):
        if len(g)!=2:continue
        home=g[g.side=='home'];away=g[g.side=='away']
        if len(home)!=1 or len(away)!=1:continue
        ph=float(home.mu.iloc[0]);pa=float(away.mu.iloc[0]);
        prob=float(np.clip(1-skellam.cdf(0,ph,pa)+.5*skellam.pmf(0,ph,pa),0,1))
        actual=int(home.runs_actual.iloc[0]>away.runs_actual.iloc[0])
        # Regulation ties have no winner: omit from this proxy diagnostic.
        if home.runs_actual.iloc[0]==away.runs_actual.iloc[0]:continue
        win.append((prob-actual)**2)
    return dict(status='retrospective holdout, not prospectively frozen',games=len(subset)//2,
       team_run_mae=bad(absnew),constant_4_5_run_mae=bad(absbase),
       mae_improvement=bad(absbase)-bad(absnew),
       improvement_95CI_day_bootstrap=paired_bootstrap(pairs),
       regulation_winner_proxy_brier=bad(win) if win else None,
       pitcher_rows_with_prior=(int((subset['opp_sp_known']>0).sum()) if 'opp_sp_known' in subset else None),
       notes='Game dates are isolated in feature building. Advanced lineup/weather overlays and inning-level Monte Carlo not evaluated here.')


def evaluate(root,as_of='2026-10-13'):
    data=Path(root)/'data';raw=all_games(data,True)
    cutoff=pd.Timestamp(as_of)
    raw=[g for g in raw if pd.Timestamp(g['date'])<cutoff]
    details,hands,_=loaded_details(data)
    games,count=enrich_games(raw,details,hands)
    games,fielding_count=add_fielding_errors(games,data)
    frame=historical_team_rows(games,hands)
    fit=train_frozen_run_model(frame)
    out={'model':'v4 frozen Poisson team-runs 2023-24','as_of_exclusive':as_of,
     'training_rows':fit.training_rows,'validation_tuned_2024_score':fit.validation_poisson_deviance,
     'detailed_team_rows_matched':count,'fielding_games_matched':fielding_count,
     'defense_feature_selected_in_2024':('opp_field_errors15' in fit.features),'validation':{}}
    for y in (2025,2026):
        for kind in ('R','P'):
            out['validation'][f'{y}_{kind}']=report(fit,frame,y,kind)
    # Compare against the PRIOR backtested run model on the IDENTICAL 2025
    # Retrosheet games, not a new or invented weaker benchmark.
    try:
        original_fit=build_run_fit(data)
        old,fields,_,_,_=original_fit
        old_frame=make_features(read_rows(data))
        old25=old_frame[old_frame.year==2025]
        old_h,old_a=preds(old,old25,fields)
        old_errors=np.concatenate([np.abs(old_h-old25.home_reg.to_numpy(dtype=float)),
                                   np.abs(old_a-old25.away_reg.to_numpy(dtype=float))])
        keymap={}
        v25=frame[(frame.year==2025)&(frame.game_type=='R')]
        predictions=predict_rates(fit,v25)
        for (_,r),pr in zip(v25.iterrows(),predictions):
            key=(str(r.date)[:10],str(r.game_num),str(r.team),str(r.opponent))
            keymap[key]=abs(float(r.runs_actual)-pr)
        daypairs=[]
        for j,(_,r) in enumerate(old25.iterrows()):
            day=str(r.date)[:10];num=str(r.game_num)
            for side,team,opp,estimate,actual in (
                ('home',r.home,r.away,old_h[j],r.home_reg),
                ('away',r.away,r.home,old_a[j],r.away_reg)):
                new=keymap.get((day,num,str(team),str(opp)))
                if new is not None:
                    daypairs.append({'date':day,'delta':abs(float(actual)-float(estimate))-new})
        ci=paired_bootstrap(daypairs) if daypairs else None
        out['original_run_model_2025']={'n_games':len(old25),
            'team_run_mae':float(old_errors.mean()),
            'v4_team_run_mae':out['validation']['2025_R']['team_run_mae'],
            'v4_minus_original_mae':out['validation']['2025_R']['team_run_mae']-float(old_errors.mean()),
            'old_minus_v4_mae_day_bootstrap_95CI':ci,
            'matched_team_observations':len(daypairs),
            'note':'Same 2025 regulation-game population; still retrospective model-development data.'}
    except Exception as exc:
        out['original_run_model_2025']={'status':'comparison unavailable','reason':str(exc)}
    out['warnings']=['No automatic model promotion',
      'Historical holdouts inspected during development; not clean prospective evaluation',
      'Individual hitter and weather overlays require separate holdout snapshots before calibration',
      'This tests expected regulation runs, not the entire inning simulator, and is not a profit test.']
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--as-of',default='2026-10-13');parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    result=evaluate(args.root,args.as_of)
    dest=args.root/'outputs'/'v4_model_validation.json';dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2));print('Saved:',dest)
