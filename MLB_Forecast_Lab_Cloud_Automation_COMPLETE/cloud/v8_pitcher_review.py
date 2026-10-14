"""Research: reassess V6.2 starter correction with V8 recency-weighted fits.

Each fold fits years <test, tuning hyperparameters was performed on earlier
years only in walkforward_2022_2025.json. Starter weight selection uses only
2022-2024 folds; 2025 is reported separately. This is retrospective research.
"""
import json,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games
from v4_defense import add_fielding_errors
from v4_matchup_core import historical_team_rows,FEATURES,_poisson_loss
from cloud.v8_walkforward import fit,FILTERS
from v62_pitching import blended_rates

WEIGHTS=(0.,.25,.5,.75,1.)

def study(root):
    started=time.monotonic();root=Path(root);data=root/'data'
    report=json.loads((root/'outputs/v8_validation/walkforward_2022_2025.json').read_text())
    games=[g for g in all_games(data,True) if g['year']<=2025]
    details,hands,_=loaded_details(data)
    enriched,_=enrich_games(games,details,hands)
    enriched,_=add_fielding_errors(enriched,data)
    frame=historical_team_rows(enriched,hands)
    folds=[]
    for fold in report['folds']:
        if fold['status']!='ok':continue
        year=int(fold['year'])
        cols=list(FEATURES) if fold['fielding_selected'] else FILTERS['no_fielding'](FEATURES)
        train=frame[(frame.year>=2016)&(frame.year<year)&(frame.game_type=='R')]
        test=frame[(frame.year==year)&(frame.game_type=='R')]
        model=fit(train,cols,float(fold['alpha']),float(fold['half_life_years']),year-1)
        frozen=SimpleNamespace(pipeline=model,features=cols)
        y=test.runs_actual.to_numpy(dtype=float)
        score={}
        for weight in WEIGHTS:
            pred,*_=blended_rates(frozen,test,weight)
            score[str(weight)]={'team_games':len(y),
                                'mae':float(np.mean(abs(pred-y))),
                                'poisson_score':float(_poisson_loss(y,pred))}
        known=int(np.sum(test.opp_sp_known.to_numpy(dtype=float)>=3))
        folds.append({'year':year,'n_team_games':len(test),'with_3plus_prior_starts':known,
                      'fraction_with_3plus_prior_starts':round(known/len(test),4),
                      'alpha':fold['alpha'],'half_life':fold['half_life_years'],
                      'scores':score})
        print('PITCHER WEIGHTS',year,'sample',len(test),'prior starts>=3',known,
              'loss0',round(score['0.0']['poisson_score'],6),
              'loss0.25',round(score['0.25']['poisson_score'],6),flush=True)
    pooled={}
    for w in WEIGHTS:
        key=str(w);n=sum(f['scores'][key]['team_games'] for f in folds)
        pooled[key]={'n_team_games':n,
                     'poisson_score':sum(f['scores'][key]['poisson_score']*f['scores'][key]['team_games'] for f in folds)/n,
                     'mae':sum(f['scores'][key]['mae']*f['scores'][key]['team_games'] for f in folds)/n}
    calibration=[f for f in folds if f['year']<=2024]
    n=sum(f['n_team_games'] for f in calibration)
    candidates=[(sum(f['scores'][str(w)]['poisson_score']*f['n_team_games'] for f in calibration)/n,w) for w in WEIGHTS]
    selected=min(candidates)[1]
    last=next((f for f in folds if f['year']==2025),None)
    return {'type':'retrospective_v8_starter_correction_ablation',
            'weights':list(WEIGHTS),'model_weights_selected_from_2022_to_2024_only':selected,
            'old_production_weight':.25,'folds':folds,'pooled':pooled,
            '2025_selected_weight_metrics':last['scores'][str(selected)] if last else None,
            '2025_old_weight_metrics':last['scores']['0.25'] if last else None,
            'runtime_seconds':round(time.monotonic()-started,2),
            'limitations':['Historical pitching coverage is uneven, especially before 2023.',
              'Regular-season mean-run evaluation does not prove playoff win/total probability accuracy.',
              '2025/2026 results have influenced previous project development and are not untouched validation.',
              'Any coefficient change requires an independently recorded later prospective comparison.']}
def main():
    root=Path(__file__).resolve().parents[1];result=study(root)
    folder=root/'outputs/v8_validation';folder.mkdir(exist_ok=True,parents=True)
    (folder/'pitcher_weight_review.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'selected_from_2022_2024':result['model_weights_selected_from_2022_to_2024_only'],
                      'pooled':result['pooled'],'runtime_seconds':result['runtime_seconds']},indent=2))
if __name__=='__main__':main()
