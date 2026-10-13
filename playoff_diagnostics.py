#!/usr/bin/env python3
"""Separate 2025 playoff stress test; bootstrap uncertainties and rest descriptives.
All p-values/intervals are descriptive, not proof of betting value.
"""
import json
from pathlib import Path
from math import sqrt
import numpy as np
import pandas as pd
from extended_eval import all_games

HERE=Path(__file__).parent


def day_cluster_interval(frame,model,base,target,B=4000,seed=26):
    g=frame.copy();g['date']=pd.to_datetime(g.date)
    d=(g[target].to_numpy()-g[base].to_numpy())**2-(g[target].to_numpy()-g[model].to_numpy())**2
    # Positive => model Brier improvement vs baseline
    per=pd.DataFrame({'date':g.date,'improvement':d}).groupby('date').improvement.apply(np.array)
    buckets=list(per);lens=np.array([len(x) for x in buckets]);sums=np.array([x.sum() for x in buckets])
    rng=np.random.default_rng(seed);ids=rng.integers(0,len(buckets),(B,len(buckets)))
    boot=sums[ids].sum(axis=1)/lens[ids].sum(axis=1)
    return {'improvement':float(d.mean()),'ci95':[float(np.quantile(boot,.025)),float(np.quantile(boot,.975))],
            'bootstrap_type':'calendar-date clustered; postseason seasons not independent'}


def rest_guide(games):
    most_recent={};by_id={}
    from itertools import groupby
    for (year,date),grp in groupby(games,key=lambda g:(g['year'],g['date'])):
        current=list(grp)
        for g in current:
            dh=(date-most_recent[g['home']]).days-1 if g['home'] in most_recent else None
            da=(date-most_recent[g['away']]).days-1 if g['away'] in most_recent else None
            by_id[g['game_id']]={'home_rest_days':dh,'away_rest_days':da}
        for g in current:
            most_recent[g['home']]=date;most_recent[g['away']]=date
    return by_id


def analyze(prediction_csv,games,baseline_home,baseline_under,output):
    predictions=pd.read_csv(prediction_csv)
    p=predictions[(predictions.year==2025)&(predictions.game_type=='P')].copy()
    if p.empty: return {'status':'not_available','n':0}
    p['base_home']=baseline_home;p['base_under']=baseline_under
    info={ 'winner':day_cluster_interval(p,'p_home_elo','base_home','actual_home_win'),
           'under_6_5':day_cluster_interval(p,'p_under_6_5_run_model','base_under','actual_under_6_5') }
    win_count=int(((p.p_home_elo>=.5)==p.actual_home_win).sum());n=len(p)
    # Wilson interval for success proportion (only sample uncertainty, not forecasting stability)
    z=1.96;obs=win_count/n;den=1+z*z/n
    center=(obs+z*z/(2*n))/den;half=z/den*sqrt(obs*(1-obs)/n+z*z/(4*n*n))
    rests=rest_guide(games)
    p['home_rest_days']=p.game_id.map(lambda k:rests.get(k,{}).get('home_rest_days'))
    p['away_rest_days']=p.game_id.map(lambda k:rests.get(k,{}).get('away_rest_days'))
    p['rest_diff_home_minus_away']=p.home_rest_days-p.away_rest_days
    subset=p[p.rest_diff_home_minus_away.notna()]
    # Deliberately descriptive; no causal effects and no parameter tuning to 2025.
    descriptive=[]
    for title,m in [('home_has_2plus_extra_days',subset.rest_diff_home_minus_away>=2),
                    ('away_has_2plus_extra_days',subset.rest_diff_home_minus_away<=-2),
                    ('rest_difference_less_than_2_days',subset.rest_diff_home_minus_away.abs()<2)]:
        x=subset[m]
        descriptive.append(dict(group=title,n=len(x),home_wins=int(x.actual_home_win.sum()),
             home_win_rate=float(x.actual_home_win.mean()) if len(x) else None))
    result={'status':'completed_single_postseason_holdout','n_games':n,
          'win_correct':win_count,'elo_win_accuracy':win_count/n,
          'elo_win_accuracy_wilson95':[center-half,center+half],
          'brier_comparison_vs_constant':info,
          'rest_difference_descriptive_only':descriptive,
          'caveat':'Only one 2025 postseason: 47 observations, clustered by series/teams and calendar dates. No sportsbook/Kalshi odds. No causal rest inference.'}
    output.mkdir(exist_ok=True,parents=True)
    p.to_csv(output/'postseason_2025_predictions_with_rest.csv',index=False)
    (output/'postseason_diagnostics.json').write_text(json.dumps(result,indent=2))
    return result


def main():
    data=HERE/'data';output=HERE/'outputs'
    games=all_games(data,True)
    stats=json.loads((output/'extended_metrics.json').read_text())
    print(json.dumps(analyze(output/'extended_predictions.csv',games,stats['base_home'],stats['base_under'],output),indent=2))

if __name__=='__main__':main()
