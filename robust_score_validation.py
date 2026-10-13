#!/usr/bin/env python3
"""Compare MLB prediction models on IDENTICAL chronological holdout games.

Run: py robust_score_validation.py --as-of 2026-10-12

Fits are frozen on 2023-24 (validation in 2024). No 2025/2026 fitting.
All features and Elo states use strictly preceding dates, not same-day scores.
The 2025/2026 data were previously inspected during development, so they
are retrospective holdouts, NOT pristine prospective validation.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import preds
from extended_eval import all_games, predict_elo
from forecast_engine import build_run_fit
from score_calibration_2026 import prior_day_frame, bootstrap_days
from score_projection import raw_final_score_matrix, align_winner_to_elo
from matchup_model import loaded_details, enrich_games, feature_frame, choose_model, COVARIATES

ROOT=Path(__file__).resolve().parent
# Keep hypotheses PREDECLARED; do not choose a 'winner' based on the holdout.
CANDIDATES=('poisson','validated_nb','wide_nb','constant_nb')


def crps_discrete(pmf, observation):
    """Proper discrete CRPS = sum over integer thresholds of squared CDF error."""
    p=np.asarray(pmf,dtype=float)
    if p.ndim!=1 or np.any(p < -1e-12) or not np.all(np.isfinite(p)):
        raise ValueError('Invalid probability distribution')
    if not np.isclose(p.sum(),1,atol=1e-7):
        raise ValueError('PMF does not sum to 1')
    if not isinstance(observation,(int,np.integer)) or observation < 0:
        raise ValueError('Observation must be a nonnegative integer')
    # Include the tail beyond the finite support if outcome exceeds the grid.
    grid=np.arange(max(len(p),observation+1))
    cdf=np.zeros(len(grid),dtype=float)
    cdf[:len(p)]=np.cumsum(p)
    cdf[len(p):]=1.0
    return float(np.sum((cdf-(grid>=observation))**2))


def discrete_interval(pmf,level=.8):
    """Central equal-tailed interval; discrete coverage is usually >= nominal."""
    if not 0<level<1:raise ValueError('Bad interval confidence')
    cdf=np.cumsum(pmf)
    lo=int(np.searchsorted(cdf,(1-level)/2))
    hi=int(np.searchsorted(cdf,1-(1-level)/2))
    return lo,hi


def score_metrics(matrix,actual_home,actual_away):
    mat=np.asarray(matrix,dtype=float)
    if mat.ndim!=2 or mat.shape[0]!=mat.shape[1] or not np.isclose(mat.sum(),1,atol=1e-7):
        raise ValueError('Invalid final score matrix')
    if actual_home<0 or actual_away<0:raise ValueError('Negative final score')
    h,a=np.indices(mat.shape)
    p_home=mat.sum(axis=1);p_away=mat.sum(axis=0)
    totals=np.bincount((h+a).ravel(),weights=mat.ravel(),minlength=mat.shape[0]*2-1)
    observed_total=int(actual_home+actual_away)
    actual_score_p=(float(mat[actual_home,actual_away]) if max(actual_home,actual_away)<mat.shape[0] else 0.)
    best_h,best_a=np.unravel_index(int(mat.argmax()),mat.shape)
    home_win=float(mat[h>a].sum()); under=float(mat[h+a<=6].sum())
    m_home=float(np.dot(np.arange(len(p_home)),p_home))
    m_away=float(np.dot(np.arange(len(p_away)),p_away))
    res={
        'home_brier':(home_win-float(actual_home>actual_away))**2,
        'under_brier':(under-float(observed_total<=6))**2,
        'exact_log_loss':-float(np.log(max(actual_score_p,1e-12))),
        'exact_hit':int(best_h==actual_home and best_a==actual_away),
        'run_mae':(abs(m_home-actual_home)+abs(m_away-actual_away))/2,
        'total_crps':crps_discrete(totals,observed_total),
        'team_runs_crps':(crps_discrete(p_home,int(actual_home))+crps_discrete(p_away,int(actual_away)))/2,
        'home_win_prob':home_win,
        'under_6_5_prob':under,
    }
    for lvl in (.8,.9):
        tag=f'pi{int(lvl*100)}'
        ranges=[discrete_interval(x,lvl) for x in (p_home,p_away,totals)]
        obs=[int(actual_home),int(actual_away),observed_total]
        res[f'{tag}_coverage'] =float(np.mean([lo<=v<=hi for (lo,hi),v in zip(ranges,obs)]))
        res[f'{tag}_width'] =float(np.mean([hi-lo for lo,hi in ranges]))
        res[f'{tag}_total_coverage']=int(ranges[2][0]<=observed_total<=ranges[2][1])
        res[f'{tag}_total_width']=int(ranges[2][1]-ranges[2][0])
    return res


def score_candidate(mu_h,mu_a,alpha_h,alpha_a,extras,elo,name,bh,ba):
    if name=='poisson':
        ah=aa=0.0
    elif name=='validated_nb':
        ah,aa=alpha_h,alpha_a
    elif name=='wide_nb':
        ah,aa=min(.9,alpha_h*1.5),min(.9,alpha_a*1.5)
    elif name=='constant_nb':
        mu_h,mu_a=bh,ba;ah,aa=alpha_h,alpha_a
    else:
        raise ValueError('Unregistered model: '+str(name))
    raw=raw_final_score_matrix(mu_h,mu_a,ah,aa,extras)
    return align_winner_to_elo(raw,elo)


def day_cluster_interval(records, left, right, measure, reps=400, seed=131):
    """Paired game-day bootstrap interval: mean(left - right). Lower is better."""
    selected=[x for x in records if left+'_'+measure in x and right+'_'+measure in x]
    if len(selected)<40 or len({x['date'] for x in selected})<10:return None
    by_day=defaultdict(list)
    for r in selected:
        by_day[r['date']].append(r[left+'_'+measure]-r[right+'_'+measure])
    values=[np.asarray(v,dtype=float) for v in by_day.values()]
    rng=np.random.default_rng(seed);m=len(values);boot=[]
    for _ in range(reps):
        ids=rng.integers(0,m,m)
        boot.append(sum(values[i].sum() for i in ids)/sum(len(values[i]) for i in ids))
    return [float(x) for x in np.quantile(boot,[.025,.975])]


def model_comparison(records, names, measure='home_brier'):
    return {name:float(np.mean([r[name+'_'+measure] for r in records])) for name in names}


def report_group(records, names):
    if not records:return {'n':0,'status':'UNAVAILABLE'}
    stats={'n':len(records),'models':{},'paired_95pct_ci_delta_vs_validated_nb':{},'selected':False}
    metrics=('home_brier','under_brier','exact_log_loss','run_mae','total_crps',
             'team_runs_crps','exact_hit','pi80_coverage','pi80_width','pi90_coverage',
             'pi90_width','pi80_total_coverage','pi80_total_width',
             'pi90_total_coverage','pi90_total_width')
    for name in names:
        stats['models'][name]={key:float(np.mean([r[name+'_'+key] for r in records])) for key in metrics
                              if name+'_'+key in records[0]}
    for name in names:
        if name=='validated_nb':continue
        stats['paired_95pct_ci_delta_vs_validated_nb'][name]={
            met: day_cluster_interval(records,name,'validated_nb',met) for met in
            ('total_crps','team_runs_crps','exact_log_loss','under_brier') if name+'_'+met in records[0]}
    return stats


def verify_exact_key_mapping(df, keys, label):
    if df.game_id.duplicated().any():
        raise ValueError(f'{label} contains duplicate game ids')
    available=set(map(str,df.game_id))
    unknown=set(map(str,keys))-available
    if unknown:raise ValueError(f'Missing {label} for {len(unknown)} targets; example: {sorted(unknown)[:2]}')


def evaluate(data_dir, output_dir, cutoff='2026-10-12', target_year=2026,
             include_expanded=True, max_games=0):
    end=date.fromisoformat(cutoff)
    if target_year<2025 or target_year>end.year:
        raise ValueError('Evaluation year must be 2025 or later, <= cutoff year')
    # Discard ALL events on or after cutoff before any feature processing.
    games=[g for g in all_games(Path(data_dir),True)
           if pd.Timestamp(g['date']).date()<end and int(g['year'])<=target_year]
    goals=[g for g in games if int(g['year'])==target_year]
    if not goals:
        return {'status':'UNAVAILABLE','reason':'No completed target-year games before cutoff',
                'target_year':target_year,'cutoff_exclusive':cutoff}
    targets=sorted(goals,key=lambda x:(str(x['date']),str(x['game_id'])))
    if max_games>0:
        targets=targets[:max_games]
    # Elo is chronological; 2026 game outcomes cannot affect earlier forecasts.
    elo=predict_elo(games)
    verify_exact_key_mapping(elo,[g['game_id'] for g in targets],'Elo')
    elo_map=dict(zip(elo.game_id.astype(str),elo.p_home_elo.astype(float)))
    # Run model is frozen to 2023–2024. All 2026 scores enter history only AFTER prior-day feature computation.
    features=prior_day_frame(games)
    assert features.game_id.is_unique
    selected=features.set_index('game_id').loc[[g['game_id'] for g in targets]]
    fit,columns,ah,aa,extras=build_run_fit(Path(data_dir))
    mh,ma=preds(fit,selected,columns)
    hist=features[(features.year.isin([2023,2024]))&(features.game_type=='R')]
    baseh=float(hist.home_reg.mean());basea=float(hist.away_reg.mean())

    expanded={}; expanded_cover={}
    if include_expanded:
        details,hands,_=loaded_details(Path(data_dir))
        enriched,_=enrich_games(games,details,hands)
        frame=feature_frame(enriched,hands)
        if frame.game_id.duplicated().any():raise ValueError('Expanded feature IDs are not unique')
        model,_=choose_model(frame)
        exframe=frame.set_index('game_id').loc[[g['game_id'] for g in targets]]
        vals=model.predict_proba(exframe[COVARIATES].to_numpy(dtype=float))[:,1]
        expanded=dict(zip(map(str,exframe.index),map(float,vals)))
        expanded_cover=dict(zip(map(str,exframe.index),map(int,((exframe.home_sp_known>0)&(exframe.away_sp_known>0)).to_numpy())))
    rows=[]
    for i,g in enumerate(targets):
        key=str(g['game_id']);p=float(elo_map[key]);home=int(g['home_final']);away=int(g['away_final'])
        r={'game_id':key,'date':pd.Timestamp(g['date']).strftime('%Y-%m-%d'),
           'year':int(g['year']),'game_type':str(g.get('game_type','R')),
           'home':str(g['home']),'away':str(g['away']),
           'actual_home_runs':home,'actual_away_runs':away,
           'p_home_elo':p,
           'elo_home_brier':(p-int(home>away))**2,
           'starting_pitcher_coverage':expanded_cover.get(key,0)}
        if include_expanded:
            exp_p=expanded[key]
            r.update(expanded_home_win_prob=exp_p,expanded_home_brier=(exp_p-int(home>away))**2)
        for name in CANDIDATES:
            dist=score_candidate(float(mh[i]),float(ma[i]),ah,aa,extras,p,name,baseh,basea)
            r.update({name+'_'+k:v for k,v in score_metrics(dist,home,away).items()})
        rows.append(r)
    splits={
        'regular': [r for r in rows if r['game_type']=='R'],
        'postseason':[r for r in rows if r['game_type']!='R'],
        'all':rows,
    }
    summary={'status':'COMPLETED','target_year':target_year,'cutoff_exclusive':cutoff,
             'training_years':[2023,2024],
             'candidate_definitions':{
                 'poisson':'Frozen 2023-24 scoring means, alpha=0',
                 'validated_nb':'Frozen scoring means, dispersion estimated on 2024 only',
                 'wide_nb':'Same scoring means, 1.5x dispersion, PREDECLARED stress test',
                 'constant_nb':'2023-24 constant runs baseline, with the same Elo adjustment',
             },
             'no_auto_model_promotion':True,
             'partial_test_mode':bool(max_games),
             'models_have_seen_holdouts_in_development':True,
             'limitations':[
                 'Both 2025 and 2026 were previously examined during iterative development; do not claim pristine independent validation.',
                 'Winner probabilities in all four score distributions are tilted to Elo. Winner Brier is therefore IDENTICAL for those four distributions.',
                 'Expanded winner model is evaluated on the same game IDs; optional imported pitcher data may change its results when added.',
                 '2024 run-dispersion validation is not an independently unseen season.',
                 'Extra innings allocate all net extra runs to the winner, a known approximation.',
                 'Predictions do not include live weather, complete confirmed batting lineups, or Kalshi execution prices.',
                 'Intervals are central discrete predictive ranges, not parameter-uncertainty confidence intervals.',
                 'Postseason sample is very small and should not support promotion decisions.',
             ],'splits':{}}
    for label,subset in splits.items():
        grp=report_group(subset,CANDIDATES)
        if subset:
            grp['winner_models']={
                'elo':{'brier':float(np.mean([x['elo_home_brier'] for x in subset])),
                       'accuracy':float(np.mean([(x['p_home_elo']>=.5)==(x['actual_home_runs']>x['actual_away_runs']) for x in subset]))}}
            if include_expanded:
                grp['winner_models']['expanded']={
                    'brier':float(np.mean([x['expanded_home_brier'] for x in subset])),
                    'accuracy':float(np.mean([(x['expanded_home_win_prob']>=.5)==(x['actual_home_runs']>x['actual_away_runs']) for x in subset])),
                    'both_starters_have_prior_detail':int(sum(x['starting_pitcher_coverage'] for x in subset))}
                grp['winner_brier_expanded_minus_elo_ci_95']=day_cluster_interval(
                    subset,'expanded','elo','home_brier')
            grp['winner_consistency']='All score candidates adjusted to Elo; expanded winner model remains a separate comparison.'
        summary['splits'][label]=grp
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    suffix=f'{target_year}_SAMPLE_{max_games}' if max_games else str(target_year)
    csv=output_dir/f'robust_validation_{suffix}_games.csv'
    js=output_dir/f'robust_validation_{suffix}.json'
    pd.DataFrame(rows).to_csv(csv,index=False)
    js.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of',default='2026-10-12')
    parser.add_argument('--target-year',type=int,default=2026)
    parser.add_argument('--no-expanded',action='store_true',help='Skip pitcher-expanded model for faster diagnostics')
    parser.add_argument('--max-games',type=int,default=0,help='TEST ONLY: process only first N games; NOT a complete backtest')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    parser.add_argument('--out-dir',type=Path,default=ROOT/'outputs')
    args=parser.parse_args()
    print('Loading historical games and frozen models...',flush=True)
    out=evaluate(args.data_dir,args.out_dir,args.as_of,args.target_year,
                 not args.no_expanded,args.max_games)
    print(f"STATUS: {out['status']}")
    if out['status']!='COMPLETED':
        print(json.dumps(out,indent=2));return
    for split_name,values in out['splits'].items():
        if not values.get('n'):continue
        print(f"{split_name}: {values['n']:,} games; lower is better",flush=True)
        for name,rec in values['models'].items():
            print(f"  {name:<15} total CRPS={rec['total_crps']:.4f}; "
                  f"exact-score log loss={rec['exact_log_loss']:.4f}; "
                  f"under-6.5 Brier={rec['under_brier']:.4f}; "
                  f"80% interval observed coverage={rec['pi80_total_coverage']:.1%}")
        winners=values.get('winner_models',{})
        if winners:
            print('  Winner Brier: '+', '.join(f"{k}={v['brier']:.4f}" for k,v in winners.items()))
    suffix=f'{args.target_year}_SAMPLE_{args.max_games}' if args.max_games else str(args.target_year)
    print(f"Saved outputs/robust_validation_{suffix}.json and _games.csv")
    if args.max_games: print('WARNING: PARTIAL SAMPLE TEST. These are NOT full-season metrics.')
    print('No model was auto-selected. Historic market profitability remains UNAVAILABLE.')

if __name__=='__main__':main()
