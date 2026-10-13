#!/usr/bin/env python3
"""Reproduce 2025 OUT-OF-SAMPLE full-game final-score evaluation.

2023-2024 is the only training data for the model and scoring distribution.
2025 outcomes are used only after forecasts were produced. Elo for each game
comes from strict prior-date ratings, with scores held until the following day.

This is a retrospective research test, not a pristine holdout for model selection:
the team models and predictors were previously inspected on 2025 outcomes.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from backtest import read_rows, make_features, preds
from extended_eval import all_games, predict_elo
from forecast_engine import build_run_fit
from score_projection import project_score, raw_final_score_matrix, align_winner_to_elo, summarize_score_matrix

ROOT=Path(__file__).resolve().parent

def run(data_dir=ROOT/'data', output_dir=ROOT/'outputs'):
    rows=read_rows(data_dir)
    frame=make_features(rows)
    val=frame[frame.year==2025].copy()
    if len(val)<1500:raise ValueError('Missing 2025 regular-season games')
    model, features, ah, aa, extra = build_run_fit(data_dir)
    hh,aa_pred=preds(model,val,features)
    historic=[g for g in all_games(data_dir,True) if g['year']<=2025]
    elo=predict_elo(historic)
    lookup={str(g['game_id']):float(g['p_home_elo']) for _,g in elo.iterrows()}
    training=frame[frame.year.isin([2023,2024])]
    bh=float(training.home_reg.mean());ba=float(training.away_reg.mean())
    total_out=[]
    misses=[]
    for ix, row in enumerate(val.itertuples(index=False)):
        key=f"retro-{row.date.strftime('%Y%m%d')}-{row.away}-{row.home}-{row.game_num}"
        if key not in lookup:
            misses.append(key);continue
        p=lookup[key]
        result=project_score(float(hh[ix]),float(aa_pred[ix]),ah,aa,extra,p)
        baseline=project_score(bh,ba,ah,aa,extra,p)
        actual_home=int(row.home_final);actual_away=int(row.away_final)
        # Expected final score includes approximate extra-inning runs, so it is
        # a fairer comparison against FINAL rather than regulation-only scores.
        def error(x):
            eh=x['expected_home_final'];ea=x['expected_away_final']
            return (abs(eh-actual_home)+abs(ea-actual_away))/2
        predicted_top=result['top_scores'][0]
        baseline_top=baseline['top_scores'][0]
        exact_model=int(predicted_top['home_runs']==actual_home and predicted_top['away_runs']==actual_away)
        exact_base=int(baseline_top['home_runs']==actual_home and baseline_top['away_runs']==actual_away)
        # Evaluate the probability assigned to the actual score using same
        # matrix as dashboard. Tiny probabilities are clipped for finite logs.
        raw=raw_final_score_matrix(float(hh[ix]),float(aa_pred[ix]),ah,aa,extra)
        mat=align_winner_to_elo(raw,p)
        bmat=align_winner_to_elo(raw_final_score_matrix(bh,ba,ah,aa,extra),p)
        value=float(mat[actual_home,actual_away]) if max(actual_home,actual_away)<len(mat) else 0
        base=float(bmat[actual_home,actual_away]) if max(actual_home,actual_away)<len(bmat) else 0
        total_out.append({'mae_model':error(result),'mae_baseline':error(baseline),
            'exact_model':exact_model,'exact_baseline':exact_base,
            'log_loss_model':-np.log(max(value,1e-12)),
            'log_loss_baseline':-np.log(max(base,1e-12)),
            'under_brier_model':(result['under_6_5_probability']-int(actual_home+actual_away<=6))**2,
            'under_brier_baseline':(baseline['under_6_5_probability']-int(actual_home+actual_away<=6))**2})
    if misses:raise ValueError(f'Missing prior-day Elo predictions for {len(misses)} games. Example: {misses[:2]}')
    n=len(total_out)
    if n<2000:raise ValueError(f'Unexpected evaluation size {n}')
    metrics={'n':n,'train_seasons':[2023,2024], 'holdout_season':2025,
         'mean_run_absolute_error_per_team':{
            'score_model':float(np.mean([x['mae_model'] for x in total_out])),
            'constant_team_run_baseline':float(np.mean([x['mae_baseline'] for x in total_out]))},
         'most_likely_exact_score_hit_rate':{
            'score_model':float(np.mean([x['exact_model'] for x in total_out])),
            'constant_team_run_baseline':float(np.mean([x['exact_baseline'] for x in total_out]))},
         'exact_score_log_loss':{
            'score_model':float(np.mean([x['log_loss_model'] for x in total_out])),
            'constant_team_run_baseline':float(np.mean([x['log_loss_baseline'] for x in total_out]))},
         'under_6_5_brier':{
            'score_model':float(np.mean([x['under_brier_model'] for x in total_out])),
            'constant_team_run_baseline':float(np.mean([x['under_brier_baseline'] for x in total_out]))},
         'baseline_regulation_home_runs':bh,'baseline_regulation_away_runs':ba,
         'caveats':['The exact-score model is exploratory, not calibrated.',
             'Extra innings are simplified: all extra runs assigned to winner.',
             'Score model uses old 2023-24 regular-season training, 2025 test.',
             'Elo determines winner marginal; run distribution determines score totals.',
             '2025 has informed previous model development; not a pristine untouched evaluation.',
             'No live lineup, weather, injuries, or independently verified pitcher matchups.']}
    output_dir.mkdir(exist_ok=True,parents=True)
    (output_dir/'score_metrics_2025.json').write_text(json.dumps(metrics,indent=2))
    print(json.dumps(metrics,indent=2))
    return metrics

if __name__=='__main__':run()
