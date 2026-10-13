#!/usr/bin/env python3
"""Chronological 2026 exact-score evaluation for MLB Prediction Lab.

Frozen 2023-24-trained run model and 2024-tuned Elo baseline.
All feature values and Elo probabilities are constructed using results dated
STRICTLY before each game day. 2026 is a holdout, not training.
No sportsbook/Kalshi prices are consulted and no edge is inferred.

Run: py score_calibration_2026.py --as-of 2026-10-12
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd

from backtest import make_features, preds
from extended_eval import all_games, predict_elo
from forecast_engine import build_run_fit
from score_projection import raw_final_score_matrix, align_winner_to_elo

ROOT = Path(__file__).resolve().parent


def prior_day_frame(games):
    """Produce pregame features; missing regulation data is a prior-game proxy.

    The target's score appears in the feature builder's input (needed only to
    update history AFTER that day's features are created). The builder itself
    groups the games by date and forecasts the entire date before updating.
    """
    copied=[]
    for game in games:
        v=game.copy()
        for reg,final in [('home_reg','home_final'),('away_reg','away_final')]:
            if pd.isna(v.get(reg)):
                v[reg]=float(v[final])
        copied.append(v)
    # Critical: make_features uses groupby on ordered year/date values.
    copied.sort(key=lambda g:(int(g['year']),pd.Timestamp(g['date']),str(g.get('game_num',''))))
    frame=make_features(copied)
    if frame['game_id'].duplicated().any():
        raise ValueError('Duplicate game IDs, cannot validate exact scores')
    return frame


def one_game(mat, true_home, true_away):
    hi, ai=np.indices(mat.shape)
    winner=hi>ai
    actual_score_probability=(float(mat[true_home,true_away]) if
        0<=true_home<mat.shape[0] and 0<=true_away<mat.shape[1] else 0.0)
    best_idx=int(np.argmax(mat))
    best_home,best_away=map(int,np.unravel_index(best_idx,mat.shape))
    fav_home=float(mat[winner].sum())>=.5
    mask=winner if fav_home else (hi<ai)
    display_idx=int(np.argmax(np.where(mask,mat,-1.0)))
    display_home,display_away=map(int,np.unravel_index(display_idx,mat.shape))
    expected_home=float((mat*hi).sum());expected_away=float((mat*ai).sum())
    actual_under=int(true_home+true_away<=6)
    predicted_under=float(mat[hi+ai<=6].sum())
    return {
        'actual_home_runs':int(true_home),'actual_away_runs':int(true_away),
        'expected_home_runs':expected_home,'expected_away_runs':expected_away,
        'top_score_home':best_home,'top_score_away':best_away,
        'top_score_probability':float(mat.flat[best_idx]),
        'top_score_correct':int(best_home==true_home and best_away==true_away),
        'display_score_home':display_home,'display_score_away':display_away,
        'display_score_probability':float(mat.flat[display_idx]),
        'display_score_correct':int(display_home==true_home and display_away==true_away),
        'actual_score_probability':actual_score_probability,
        'exact_score_log_loss':-float(np.log(max(actual_score_probability,1e-12))),
        'mean_absolute_error_per_team':(abs(expected_home-true_home)+abs(expected_away-true_away))/2,
        'under_6_5_probability':predicted_under,
        'under_6_5_brier':(predicted_under-actual_under)**2,
        'home_win_probability':float(mat[winner].sum()),
        'home_win_brier':(float(mat[winner].sum())-int(true_home>true_away))**2,
    }


def wilson_interval(hit, n, z=1.96):
    if n==0:return [None,None]
    p=hit/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*np.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [float(max(0,center-half)),float(min(1,center+half))]


def calibration_bins(records, edges=(0,.02,.03,.04,.05,.06,.08,.10,1.01)):
    """Bin the probability assigned to the selected modal exact score.

    This is a conditional top-pick calibration diagnostic, not full multiclass
    calibration (which requires reliability tests for all score cells).
    """
    out=[]
    for lo,hi in zip(edges[:-1],edges[1:]):
        selected=[r for r in records if lo<=r['top_score_probability']<hi]
        if not selected:continue
        n=len(selected);wins=sum(x['top_score_correct'] for x in selected)
        out.append({'range':f'{lo:.1%}–{min(1,hi):.1%}','games':n,
            'mean_predicted_probability':float(np.mean([x['top_score_probability'] for x in selected])),
            'observed_frequency':wins/n,'correct_top_scores':wins,
            'observed_95pct_wilson':wilson_interval(wins,n)})
    return out


def summarize(records):
    if not records:return {'n':0,'status':'UNAVAILABLE'}
    result={'n':len(records)}
    for metric in ('mean_absolute_error_per_team','top_score_correct','exact_score_log_loss',
                   'display_score_correct','under_6_5_brier','home_win_brier'):
        result[metric]={label:float(np.mean([r[f'{prefix}_{metric}'] for r in records]))
                        for prefix,label in [('model','score_model'),('baseline','constant_runs_baseline')]}
        result[metric]['model_minus_baseline']=result[metric]['score_model']-result[metric]['constant_runs_baseline']
    result['exact_score_top_pick_calibration']=calibration_bins([
        {'top_score_probability':r['model_top_score_probability'],
         'top_score_correct':r['model_top_score_correct']} for r in records])
    result['displayed_winning_score_calibration']=calibration_bins([
        {'top_score_probability':r['model_display_score_probability'],
         'top_score_correct':r['model_display_score_correct']} for r in records])
    result['overall_displayed_score_predicted_probability']=float(np.mean([r['model_display_score_probability'] for r in records]))
    result['overall_displayed_score_actual_hit_rate']=float(np.mean([r['model_display_score_correct'] for r in records]))
    result['overall_top_pick_predicted_probability']=float(np.mean([r['model_top_score_probability'] for r in records]))
    result['overall_top_pick_actual_hit_rate']=float(np.mean([r['model_top_score_correct'] for r in records]))
    return result


def bootstrap_days(records, metric, n_boot=500, seed=42):
    """Paired confidence interval for model-minus-baseline by resampling days."""
    if len(records)<30:return None
    by_day=defaultdict(list)
    for r in records:
        by_day[r['date']].append(r[f'model_{metric}']-r[f'baseline_{metric}'])
    d=list(by_day)
    if len(d)<10:return None
    grouped=[np.array(by_day[day],dtype=float) for day in d]
    rng=np.random.default_rng(seed)
    estimates=[]
    for _ in range(n_boot):
        picks=rng.integers(0,len(d),size=len(d))
        total=sum(grouped[i].sum() for i in picks)
        count=sum(len(grouped[i]) for i in picks)
        estimates.append(total/count)
    lo,hi=np.percentile(estimates,[2.5,97.5])
    return [float(lo),float(hi)]


def evaluate(data_dir, output_dir, cutoff='2026-10-12', include_2025=False):
    cutoff_day=date.fromisoformat(cutoff)
    games=[g for g in all_games(data_dir, True)
           if pd.Timestamp(g['date']).date()<cutoff_day]
    target_year=2025 if include_2025 else 2026
    games=[g for g in games if int(g['year'])<=target_year]
    targets=[g for g in games if int(g['year'])==target_year]
    if not targets:
        return {'status':'UNAVAILABLE','reason':f'No final {target_year} games before cutoff; import game data first.',
                'target_year':target_year,'cutoff_exclusive':cutoff}
    # Do not use game outcomes after the selected cutoff anywhere in feature history.
    elo_frame=predict_elo(games)
    p_elo={str(r.game_id):float(r.p_home_elo) for r in elo_frame.itertuples()}
    feature_frame=prior_day_frame(games)
    x=feature_frame[(feature_frame.year==target_year)].copy()
    models,feature_names,alpha_h,alpha_a,extras=build_run_fit(data_dir)
    mus_h,mus_a=preds(models,x,feature_names)
    train=feature_frame[(feature_frame.year.isin([2023,2024])) &
                        (feature_frame.get('game_type','R')=='R')]
    bh=float(train.home_reg.mean()); ba=float(train.away_reg.mean())
    records=[]
    for i,g in enumerate(x.to_dict('records')):
        key=str(g['game_id'])
        if key not in p_elo:raise ValueError(f'Missing historical Elo prediction for {key}')
        p=p_elo[key]
        actual_h=int(g['home_final']); actual_a=int(g['away_final'])
        raw=raw_final_score_matrix(float(mus_h[i]),float(mus_a[i]),alpha_h,alpha_a,extras)
        braw=raw_final_score_matrix(bh,ba,alpha_h,alpha_a,extras)
        model=one_game(align_winner_to_elo(raw,p),actual_h,actual_a)
        base=one_game(align_winner_to_elo(braw,p),actual_h,actual_a)
        rec={'game_id':key,'date':str(pd.Timestamp(g['date']).date()),
             'game_type':str(g.get('game_type','R')),
             'home':str(g['home']),'away':str(g['away']),
             'actual_home_runs':actual_h,'actual_away_runs':actual_a,
             'p_home_elo':p,'run_model_expected_home_reg':float(mus_h[i]),
             'run_model_expected_away_reg':float(mus_a[i])}
        rec.update({f'model_{k}':v for k,v in model.items()})
        rec.update({f'baseline_{k}':v for k,v in base.items()})
        records.append(rec)
    # Most user-visible diagnostics, separated by regular season and postseason.
    summary={'status':'COMPLETED','target_year':target_year,'cutoff_exclusive':cutoff,
        'training_seasons':[2023,2024],
        'limitations':[
            'No 2026 final scores are used to fit the run scoring model.',
            'Past completed game scores can enter the next game date feature history (normal chronological updating).',
            'Some missing regulation innings in earlier MLB API game records use past final runs as a noisy proxy.',
            'Same-day results never enter that day’s forecasts.',
            'The exact-score model uses simplified extra-inning run allocation.',
            'Elo winner probabilities are used to adjust the score distribution.',
            'Calibration of the single most likely score is not full score-matrix calibration.',
            '2025 results were consulted during model development; 2026 is a more independent test but not a proof of wagering profitability.',
            'No actual historical betting prices or fees were tested.'],
        'regular_2026_or_requested_year':summarize([r for r in records if r['game_type']=='R']),
        'postseason_2026_or_requested_year':summarize([r for r in records if r['game_type']!='R']),
        'combined':summarize(records),
        'day_cluster_bootstrap_95pct_delta_model_minus_baseline':{
            k:bootstrap_days(records,k) for k in
                ('mean_absolute_error_per_team','exact_score_log_loss','under_6_5_brier','top_score_correct','display_score_correct')},
    }
    output_dir.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(records).to_csv(output_dir/f'score_calibration_{target_year}_games.csv',index=False)
    (output_dir/f'score_calibration_{target_year}.json').write_text(json.dumps(summary,indent=2))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of',default='2026-10-12')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    parser.add_argument('--out-dir',type=Path,default=ROOT/'outputs')
    parser.add_argument('--validation-2025',action='store_true',
                        help='Check behavior on 2025; this is NOT the independent 2026 test')
    args=parser.parse_args()
    result=evaluate(args.data_dir,args.out_dir,args.as_of,args.validation_2025)
    if result['status']!='COMPLETED':
        print(json.dumps(result,indent=2));return
    def pretty(r):
        if not r['n']:return 'unavailable'
        return (f"{r['n']:,} games; score-model MAE {r['mean_absolute_error_per_team']['score_model']:.3f} "
                f"vs baseline {r['mean_absolute_error_per_team']['constant_runs_baseline']:.3f}; "
                f"exact-score hit {r['top_score_correct']['score_model']:.2%} "
                f"vs baseline {r['top_score_correct']['constant_runs_baseline']:.2%}; "
                f"log loss {r['exact_score_log_loss']['score_model']:.3f} "
                f"vs baseline {r['exact_score_log_loss']['constant_runs_baseline']:.3f}")
    print(f"2026 SCORE VALIDATION: cutoff {args.as_of} (exclusive)")
    print('Regular season:',pretty(result['regular_2026_or_requested_year']))
    print('Postseason:',pretty(result['postseason_2026_or_requested_year']))
    print('Combined:',pretty(result['combined']))
    print('Top-score calibration bins:')
    for item in result['combined']['exact_score_top_pick_calibration']:
        print(f"  {item['range']}: {item['games']} games, predicted {item['mean_predicted_probability']:.2%}, observed {item['observed_frequency']:.2%}")
    print(f"Saved outputs/score_calibration_{result['target_year']}.json and games.csv")

if __name__=='__main__':main()
