"""2025 holdout comparison and day-cluster paired bootstrap intervals.
Data copyright Retrosheet (www.retrosheet.org).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

P=Path(__file__).parent
withstart=pd.read_csv(P/'results_with_starter'/'holdout_predictions_2025.csv')
nostart=pd.read_csv(P/'results_no_starter'/'holdout_predictions_2025.csv')
elo=pd.read_csv(P/'results_elo'/'holdout_elo_predictions_2025.csv')
assert len(withstart)==len(nostart)==len(elo)==2425
for col in ('date','home','away'):
    assert np.array_equal(withstart[col].to_numpy(),elo[col].to_numpy())
    assert np.array_equal(withstart[col].to_numpy(),nostart[col].to_numpy())
train=json.load(open(P/'results_with_starter'/'metrics.json'))['metadata']
basewin=train['training_constant_home_win'];baseunder=train['training_constant_under_6_5']
full=withstart.copy()
full=full.rename(columns={'pred_home_win':'p_win_runmodel_with_starter','pred_under_6_5':'p_under_runmodel_with_starter'})
full['p_win_runmodel_no_starter']=nostart['pred_home_win'].to_numpy()
full['p_under_runmodel_no_starter']=nostart['pred_under_6_5'].to_numpy()
full['p_win_elo']=elo['p_home'].to_numpy()
full['p_win_constant']=basewin
full['p_under_constant']=baseunder

def met(y,p):
    y=np.asarray(y);p=np.asarray(p)
    return {'accuracy':round(float(np.mean((p>=.5)==y)),4),
            'brier':round(float(np.mean((p-y)**2)),5),
            'log_loss':round(float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))),5),
            'mean_predicted':round(float(p.mean()),4),'actual':round(float(y.mean()),4)}

# Each calendar date is a resampling unit; avoids assuming that all games on a date are independent.
rng=np.random.default_rng(20261012)
dates,inv=np.unique(full.date.to_numpy(),return_inverse=True)
ind=[np.flatnonzero(inv==i) for i in range(len(dates))]
def ci_improvement(y,p,base,reps=2500):
    d=(np.asarray(base)-y)**2-(np.asarray(p)-y)**2
    sumd=np.array([d[x].sum() for x in ind]); sizes=np.array([len(x) for x in ind]);
    result=np.empty(reps)
    for k in range(reps):
        draw=rng.integers(0,len(dates),size=len(dates))
        result[k]=sumd[draw].sum()/sizes[draw].sum()
    return {'brier_improvement':round(float(d.mean()),6),
            'bootstrap_ci_95':list(np.round(np.quantile(result,[.025,.975]),6)),
            'resampling':'calendar-date-cluster bootstrap','bootstrap_replicates':reps}

win=full.actual_home_win.to_numpy()
under=full.actual_under_6_5.to_numpy()
res={'notes':['Retrosheet 2023-2024 training and 2024 Elo validation; 2025 held-out test.',
              'Games on the same date have no mutual outcome leakage into features.',
              'This data contains regular-season games, not playoffs.',
              'No sportsbook or Kalshi quotes were available, so profitability was not tested.'],
     'test_games':len(full),'test_dates':len(dates),
     'winner_models':{},'under_6_5_models':{}}
for col in ['p_win_constant','p_win_elo','p_win_runmodel_with_starter','p_win_runmodel_no_starter']:
    p=full[col].to_numpy()
    res['winner_models'][col]=met(win,p)
    if col!='p_win_constant':
        res['winner_models'][col]['vs_constant']=ci_improvement(win,p,full.p_win_constant.to_numpy())
for col in ['p_under_constant','p_under_runmodel_with_starter','p_under_runmodel_no_starter']:
    p=full[col].to_numpy()
    res['under_6_5_models'][col]=met(under,p)
    if col!='p_under_constant':
        res['under_6_5_models'][col]['vs_constant']=ci_improvement(under,p,full.p_under_constant.to_numpy())

# Report calibration in coarse bands; enforce >=30 events to avoid misleading tiny cells.
for name,col,y in [('elo','p_win_elo',win),('runmodel_win','p_win_runmodel_with_starter',win),('runmodel_under','p_under_runmodel_with_starter',under)]:
    p=full[col].to_numpy()
    bins=pd.cut(p, bins=np.arange(0,1.0001,.1), include_lowest=True)
    tb=pd.DataFrame({'bin':bins,'p':p,'y':y}).groupby('bin',observed=False).agg(n=('y','size'),predicted=('p','mean'),observed=('y','mean'))
    res.setdefault('calibration',{})[name]=[{'range':str(idx),'n':int(row['n']),
           'predicted':round(float(row['predicted']),3) if row['n'] else None,
           'observed':round(float(row['observed']),3) if row['n'] else None}
           for idx,row in tb.iterrows() if row['n']>=30]
(P/'results_comparison.json').write_text(json.dumps(res,indent=2))
full.to_csv(P/'holdout_predictions_2025_ALL_MODELS.csv',index=False)
print(json.dumps({k:v for k,v in res.items() if k!='calibration'},indent=2))
