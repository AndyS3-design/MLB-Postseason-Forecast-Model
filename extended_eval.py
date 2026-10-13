#!/usr/bin/env python3
"""Fixed-parameter Elo and run-probability validation, with chronological 2026/postseason tests.

2024-tuned Elo parameters fixed before 2025/2026 tests: K=8, home advantage 20,
carryover .75. No outcome from a date is used to predict other games on same date.
Optional MLB API game records must be provided by ingest_mlb.py. No invented data.
"""
import argparse
import json
from collections import defaultdict
from itertools import groupby
from pathlib import Path
import numpy as np
import pandas as pd
from backtest import read_rows,make_features,train,preds,dispersion,extra_model,game_probs,metrics,FEATURE_NAMES

K=8;HOME_ELO=20;OFFSEASON=.75
FIELDS=['game_id','date','first_pitch_utc','year','game_type','away','home','away_final','home_final',
        'away_reg','home_reg','away_sp','home_sp','source']


def all_games(data_dir,with_api):
    games=read_rows(data_dir)
    for g in games:
        g['game_type']='R'
        g['source']='Retrosheet game log'
        g['game_id']=f"retro-{g['date'].strftime('%Y%m%d')}-{g['away']}-{g['home']}-{g['game_num']}"
    n_extra=0
    if with_api:
        for fname in ('mlb_2026_regular.csv','mlb_postseason_2023_2026.csv'):
            path=data_dir/fname
            if not path.exists():continue
            api=pd.read_csv(path,dtype={'game_id':str})
            for r in api.to_dict('records'):
                try:
                    d=pd.Timestamp(r['date']); yr=int(r['year'])
                    if yr not in (2023,2024,2025,2026):continue
                    if str(r['game_type'])=='R' and yr!=2026:continue
                    if pd.isna(r['home_final']) or pd.isna(r['away_final']):continue
                    g=dict(date=d,year=yr,game_num=str(r['game_id']),game_id='api-'+str(r['game_id']),
                      game_type='R' if r['game_type']=='R' else 'P',away=str(r['away']),home=str(r['home']),
                      away_final=int(r['away_final']),home_final=int(r['home_final']),
                      away_reg=float(r['away_reg']) if pd.notna(r.get('away_reg')) else np.nan,
                      home_reg=float(r['home_reg']) if pd.notna(r.get('home_reg')) else np.nan,
                      away_sp='',home_sp='',source='MLB Stats API')
                    if g['away']==g['home'] or g['away_final']==g['home_final']:raise ValueError('Invalid final score')
                    games.append(g);n_extra+=1
                except (ValueError,TypeError,KeyError) as exc:
                    raise ValueError(f'Bad MLB API file row from {path}: {r}') from exc
    games.sort(key=lambda g:(g['year'],g['date'],g['game_type']!='R',g['game_num']))
    df=pd.DataFrame(games)
    if df.duplicated(subset=['year','date','home','away','game_type','game_num']).any():
        raise ValueError('Repeated game identities')
    return games


def predict_elo(games):
    ratings={};last_year=None;rows=[]
    for (yr,dt),grp in groupby(games,key=lambda g:(g['year'],g['date'])):
        gs=list(grp)
        if yr!=last_year:
            if last_year is not None:ratings={t:v*OFFSEASON for t,v in ratings.items()}
            last_year=yr
        deltas=defaultdict(float)
        for g in gs:
            h=ratings.get(g['home'],0);a=ratings.get(g['away'],0)
            p=1/(1+10**((a-h-HOME_ELO)/400))
            outcome=int(g['home_final']>g['away_final'])
            rows.append(dict(game_id=g['game_id'],date=g['date'],year=yr,game_type=g['game_type'],
                      away=g['away'],home=g['home'],p_home_elo=p,actual_home_win=outcome,
                      home_final=g['home_final'],away_final=g['away_final'],
                      actual_under_6_5=int(g['home_final']+g['away_final']<=6)))
            delta=K*(outcome-p)
            deltas[g['home']]+=delta;deltas[g['away']]-=delta
        for team,shift in deltas.items():ratings[team]=ratings.get(team,0)+shift
    return pd.DataFrame(rows)


def get_run_preds(games):
    # Some manually sourced postseason scores lack regulation innings. To keep
    # the chronology valid, use FINAL runs as a known, prior-game proxy for the
    # *rolling offense features* of later games; never claim they are regulation
    # scores. This impacts only the experimental postseason portion, not the
    # 2023-24 regular-season fit. Crucially, values from a game are appended
    # only AFTER features for all games on that date were generated.
    copied=[]; approximate=0
    for g in games:
        x=g.copy()
        for key,finalkey in [('home_reg','home_final'),('away_reg','away_final')]:
            if not np.isfinite(float(x[key])):
                x[key]=float(x[finalkey]);approximate+=1
        copied.append(x)
    # All game classes are chronologically ordered. Predictors use strictly prior dates.
    frame=make_features(copied)
    train23=frame[(frame.year==2023)&(frame.game_type=='R')]
    val24=frame[(frame.year==2024)&(frame.game_type=='R')]
    training=frame[(frame.year.isin([2023,2024]))&(frame.game_type=='R')]
    if min(len(train23),len(val24))<2000:return pd.DataFrame(),'Insufficient regular-season training data'
    features=[c for c in FEATURE_NAMES if '_sp_' not in c]
    pre=train(train23,features)
    muval=preds(pre,val24,features)
    ah=dispersion(muval[0],val24.home_reg)
    aa=dispersion(muval[1],val24.away_reg)
    models=train(training,features)
    test=frame[((frame.year>=2025)&(frame.game_type=='R'))|
               ((frame.year>=2025)&(frame.game_type=='P'))].copy()
    if test.empty:return pd.DataFrame(),'No holdout games'
    mus=preds(models,test,features)
    extra=extra_model(training)
    p=np.array([game_probs(float(h),float(a),ah,aa,extra) for h,a in zip(*mus)])
    out=test[['game_id','date']].copy()
    out['p_home_run_model']=p[:,0]
    out['p_under_6_5_run_model']=p[:,1]
    return out,(f'Run model trained on 2023-2024 regular season; no starter identity used. '
                f'{approximate} missing regulation team-scores replaced by known final scores '
                'as prior-game rolling-feature proxies; postseason run results are experimental.')


def summarize(group,base_home,base_under):
    out={'n':len(group)}
    if not len(group):return out
    out['elo_winner']=metrics(group.actual_home_win,group.p_home_elo)
    out['constant_home_baseline']=metrics(group.actual_home_win,np.repeat(base_home,len(group)))
    if 'p_under_6_5_run_model' in group and group.p_under_6_5_run_model.notna().all():
        out['run_model_under_6_5']=metrics(group.actual_under_6_5,group.p_under_6_5_run_model)
        out['run_model_home_winner']=metrics(group.actual_home_win,group.p_home_run_model)
        out['constant_under_baseline']=metrics(group.actual_under_6_5,np.repeat(base_under,len(group)))
    return out


def evaluate(games,output):
    preds_elo=predict_elo(games)
    p_run,run_status=get_run_preds(games)
    if len(p_run):
        preds_elo=preds_elo.merge(p_run,on=['game_id','date'],how='left',validate='one_to_one')
    frame=pd.DataFrame(games)
    baseline=frame[(frame.year.isin([2023,2024]))&(frame.game_type=='R')]
    base_home=float((baseline.home_final>baseline.away_final).mean())
    base_under=float(((baseline.home_final+baseline.away_final)<=6).mean())
    specs={
     'regular_2025':(preds_elo.year==2025)&(preds_elo.game_type=='R'),
     'postseason_2025':(preds_elo.year==2025)&(preds_elo.game_type=='P'),
     'regular_2026':(preds_elo.year==2026)&(preds_elo.game_type=='R'),
     'postseason_2026_before_cutoff':(preds_elo.year==2026)&(preds_elo.game_type=='P'),
     'september_2025_regular':(preds_elo.year==2025)&(preds_elo.game_type=='R')&(preds_elo.date.dt.month==9)
    }
    res={'model':'Fixed 2024-tuned Elo + no-starter 2023-24 trained run model',
         'cutoff':'2026-10-12 exclusive (unless input updated with other date)',
         'input_record_count':len(games),'run_status':run_status,
         'base_home':base_home,'base_under':base_under,
         'splits':{n:summarize(preds_elo[mask],base_home,base_under) for n,mask in specs.items()}}
    output.mkdir(exist_ok=True,parents=True)
    preds_elo[preds_elo.year>=2025].to_csv(output/'extended_predictions.csv',index=False)
    (output/'extended_metrics.json').write_text(json.dumps(res,indent=2))
    return res


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'data')
    p.add_argument('--out-dir',type=Path,default=Path(__file__).parent/'outputs')
    p.add_argument('--no-api',action='store_true',help='2023-25 baseline only')
    a=p.parse_args()
    games=all_games(a.data_dir,not a.no_api)
    res=evaluate(games,a.out_dir)
    print(json.dumps(res,indent=2))
    missing=[k for k,v in res['splits'].items() if not v['n']]
    if missing:print('UNAVAILABLE HOLDOUTS:',', '.join(missing),'\nNo result is invented for an unavailable split.')

if __name__=='__main__':main()
