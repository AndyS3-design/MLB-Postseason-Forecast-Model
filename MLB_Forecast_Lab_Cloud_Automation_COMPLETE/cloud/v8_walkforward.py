"""Time-ordered 2022-2025 regular-season Poisson feature-ablation study.
Each year: tune on previous year, train earlier only, evaluate current year.
Historical feature rows are already strictly previous-game-day.
"""
import json,time,argparse
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import PoissonRegressor
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games
from v4_defense import add_fielding_errors
from v4_matchup_core import historical_team_rows,FEATURES,_poisson_loss

FILTERS={
 'full':lambda fs:list(fs),
 'no_starters':lambda fs:[f for f in fs if not f.startswith('opp_sp_')],
 'no_bullpen':lambda fs:[f for f in fs if not f.startswith('opp_bp_') and f!='opp_manager_bp_use'],
 'no_starters_no_bullpen':lambda fs:[f for f in fs if not f.startswith('opp_sp_') and not f.startswith('opp_bp_') and f!='opp_manager_bp_use'],
 'no_fielding':lambda fs:[f for f in fs if not f.startswith('opp_field_errors') and not f.startswith('opp_errors_known')],
}

def fit(frame,columns,alpha,half_life,reference_year):
    model=make_pipeline(StandardScaler(),PoissonRegressor(alpha=alpha,max_iter=300))
    w=np.power(.5,np.maximum(0,reference_year-frame.year.to_numpy(dtype=float))/half_life)
    model.fit(frame[columns].to_numpy(dtype=float),frame.runs_actual.to_numpy(dtype=float),
              standardscaler__sample_weight=w,poissonregressor__sample_weight=w)
    return model

def evaluate(frame,pred):
    y=frame.runs_actual.to_numpy(dtype=float);p=np.clip(np.asarray(pred,dtype=float),.05,20)
    return {'team_games':len(y),'mae':float(np.mean(abs(p-y))),
            'poisson_score':float(_poisson_loss(y,p)),
            'mean_predicted_runs':float(np.mean(p)),'mean_actual_runs':float(np.mean(y))}

def study(root,years=(2022,2023,2024,2025)):
    t=time.monotonic();root=Path(root);data=root/'data'
    games=[g for g in all_games(data,True) if g['year']<=2025]
    details,hands,_=loaded_details(data)
    enriched,_=enrich_games(games,details,hands)
    enriched,_=add_fielding_errors(enriched,data)
    frame=historical_team_rows(enriched,hands)
    available=sorted(int(y) for y in frame[frame.game_type=='R'].year.unique())
    result={'type':'retrospective_nested_chronological_validation','years_available':available,
            'warning':'2022-2025 outcomes were not untouched by earlier development; prospective games remain decisive.',
            'rule':'For test year Y choose settings using Y-1, refit using years strictly before Y, evaluate Y.',
            'folds':[]}
    for year in years:
        val=frame[(frame.year==year-1)&(frame.game_type=='R')]
        earlier=frame[(frame.year>=2016)&(frame.year<year-1)&(frame.game_type=='R')]
        holdout=frame[(frame.year==year)&(frame.game_type=='R')]
        if min(len(val),len(holdout))<4000 or len(earlier)<2000:
            result['folds'].append({'year':year,'status':'insufficient_rows','test_rows':len(holdout)})
            continue
        candidates=[]
        for half in (2.,3.,5.):
            for alpha in (.1,1.,10.):
                for keep_fielding in (False,True):
                    cols=FEATURES if keep_fielding else FILTERS['no_fielding'](FEATURES)
                    m=fit(earlier,cols,alpha,half,year-2)
                    score=evaluate(val,m.predict(val[cols].to_numpy(dtype=float)))
                    candidates.append((score['poisson_score'],alpha,half,keep_fielding))
        loss,alpha,half,fielding=min(candidates)
        train=frame[(frame.year>=2016)&(frame.year<year)&(frame.game_type=='R')]
        cols=list(FEATURES) if fielding else FILTERS['no_fielding'](FEATURES)
        scores={}
        for name,filter_columns in FILTERS.items():
            selected=cols if name=='full' else filter_columns(cols)
            m=fit(train,selected,alpha,half,year-1)
            scores[name]={**evaluate(holdout,m.predict(holdout[selected].to_numpy(dtype=float))),
                          'features':selected}
        scores['constant_runs_baseline']=evaluate(holdout,np.full(len(holdout),train.runs_actual.mean()))
        result['folds'].append({'year':year,'status':'ok','train_years':sorted(int(x) for x in train.year.unique()),
            'validation_year':year-1,'alpha':alpha,'half_life_years':half,
            'fielding_selected':fielding,'validation_poisson_score':loss,'results':scores})
        print(f"WALKFORWARD {year} test_teams={len(holdout)} full_loss={scores['full']['poisson_score']:.6f} no_sp={scores['no_starters']['poisson_score']:.6f} no_bp={scores['no_bullpen']['poisson_score']:.6f}",flush=True)
    ok=[f for f in result['folds'] if f['status']=='ok']
    pooled={}
    for name in (*FILTERS,'constant_runs_baseline'):
        n=sum(f['results'][name]['team_games'] for f in ok)
        if n:
            pooled[name]={'team_games':n,'poisson_score':sum(f['results'][name]['poisson_score']*f['results'][name]['team_games'] for f in ok)/n,
                          'mae':sum(f['results'][name]['mae']*f['results'][name]['team_games'] for f in ok)/n}
    result['pooled_metrics']=pooled;result['runtime_seconds']=round(time.monotonic()-t,2)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--out',type=Path);args=p.parse_args()
    result=study(args.root)
    path=args.out or args.root/'outputs/v8_validation/walkforward_2022_2025.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
    print(json.dumps({'pooled_metrics':result['pooled_metrics'],'runtime_seconds':result['runtime_seconds']},indent=2))
if __name__=='__main__':main()
