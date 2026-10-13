"""Simple, date-strict Elo baseline; 2024 tuning, 2025 untouched final holdout.
Data copyright Retrosheet, www.retrosheet.org.
"""
import json
import numpy as np
import pandas as pd
from backtest import read_rows
from pathlib import Path
from scipy.special import expit

def elo_probs(games, home_adv, k, offseason):
    rates={}
    output=[]
    prev=None
    from itertools import groupby
    for (year,date),gp in groupby(games,key=lambda r:(r['year'],r['date'])):
        today=list(gp)
        if prev!=year:
            if prev is not None:
                rates={team:r*offseason for team,r in rates.items()}
            prev=year
        predictions=[]
        for g in today:
            rh=rates.get(g['home'],0);ra=rates.get(g['away'],0)
            p=1/(1+10**((ra-rh-home_adv)/400))
            predictions.append((g,p,rh,ra))
            output.append((g['year'],date,g['home'],g['away'],p, int(g['home_final']>g['away_final'])))
        changes={}
        for g,p,rh,ra in predictions:
            d=k*(int(g['home_final']>g['away_final'])-p)
            changes[g['home']]=changes.get(g['home'],0)+d
            changes[g['away']]=changes.get(g['away'],0)-d
        for team,d in changes.items():rates[team]=rates.get(team,0)+d
    return pd.DataFrame(output,columns=['year','date','home','away','p_home','actual_home'])

def brier(g):return float(np.mean((g.p_home-g.actual_home)**2))

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'data');p.add_argument('--out-dir',type=Path,default=Path(__file__).parent/'results_elo');args=p.parse_args()
    games=read_rows(args.data_dir)
    candidates=[]
    for k in [8,12,16,20,28]:
        for ha in [20,30,40,50]:
            for off in [.55,.75,.9]:
                preds=elo_probs(games,ha,k,off)
                val=preds[preds.year==2024]
                candidates.append((brier(val),k,ha,off))
    candidates.sort()
    _,k,ha,off=candidates[0]
    preds=elo_probs(games,ha,k,off)
    test=preds[preds.year==2025]
    p=test.p_home.to_numpy();y=test.actual_home.to_numpy()
    metrics={'method':'Elo','validation_year':2024,'test_year':2025,'validation_brier':candidates[0][0],
            'tuned_k':k,'tuned_home_adv':ha,'tuned_offseason_factor':off,'holdout_n':len(test),
            'holdout_brier':brier(test),'holdout_accuracy':float(np.mean((p>=.5)==y)),
            'holdout_logloss':float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))),
            'holdout_mean_prediction':float(p.mean()),'holdout_home_rate':float(y.mean())}
    args.out_dir.mkdir(exist_ok=True,parents=True)
    (args.out_dir/'metrics.json').write_text(json.dumps(metrics,indent=2))
    test.to_csv(args.out_dir/'holdout_elo_predictions_2025.csv',index=False)
    print(json.dumps(metrics,indent=2))

if __name__=='__main__': main()
