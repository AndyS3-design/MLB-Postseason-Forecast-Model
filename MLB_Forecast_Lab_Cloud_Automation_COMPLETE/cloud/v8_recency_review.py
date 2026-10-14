"""Research-only: compare historical recency half-lives without 2025 in tuning.

Tune regularization and fielding feature inclusion on 2024 using <=2023 training,
fit through 2024, and evaluate 2025. These are retrospective, not independent
holdouts; 2025 has influenced prior versions of this project.
"""
from __future__ import annotations
from pathlib import Path
import json,time
import numpy as np
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games
from v4_defense import add_fielding_errors
from v4_matchup_core import historical_team_rows,FEATURES
from cloud.v8_walkforward import fit,FILTERS,evaluate

HALF_LIVES=(2.0,3.0,5.0)
ALPHAS=(0.1,1.0,10.0)

def study(root):
    started=time.monotonic();root=Path(root);data=root/'data'
    games=[g for g in all_games(data,True) if int(g['year'])<=2025]
    details,hands,_=loaded_details(data)
    enriched,_=enrich_games(games,details,hands)
    enriched,_=add_fielding_errors(enriched,data)
    frame=historical_team_rows(enriched,hands)
    frame=frame[(frame.game_type=='R')&(frame.year>=2016)&(frame.year<=2025)]
    tr=frame[frame.year<=2023]
    validation=frame[frame.year==2024]
    refit=frame[frame.year<=2024]
    test=frame[frame.year==2025]
    if min(len(tr),len(validation),len(test))<3000:
        raise RuntimeError(f'Insufficient seasons: train={len(tr)}, val={len(validation)}, test={len(test)}')
    rows={}
    for half in HALF_LIVES:
        choices=[]
        for alpha in ALPHAS:
            for fielding in (False,True):
                columns=list(FEATURES) if fielding else FILTERS['no_fielding'](FEATURES)
                model=fit(tr,columns,alpha,half,2023)
                score=evaluate(validation,model.predict(validation[columns].to_numpy(dtype=float)))
                choices.append((score['poisson_score'],alpha,fielding))
        best_loss,alpha,fielding=min(choices)
        columns=list(FEATURES) if fielding else FILTERS['no_fielding'](FEATURES)
        model=fit(refit,columns,alpha,half,2024)
        pred=model.predict(test[columns].to_numpy(dtype=float))
        rows[str(half)]={'half_life':half,'validation_poisson_score':float(best_loss),
               'selected_alpha':alpha,'selected_fielding':fielding,
               '2025_test':evaluate(test,pred),'train_seasons':sorted(int(y) for y in refit.year.unique()),
               'tuned_only_on_2024':True}
        print('RECENCY',half,'2024_score',round(best_loss,6),
              '2025_score',round(rows[str(half)]['2025_test']['poisson_score'],6),
              '2025_mae',round(rows[str(half)]['2025_test']['mae'],5),flush=True)
    chosen=min(rows.values(),key=lambda r:(r['validation_poisson_score'],r['half_life']))['half_life']
    return {'type':'retrospective_recency_half_life_review','rows':rows,
       'selected_using_2024_only':chosen,
       '2025_prechosen_weight_vs_fixed3':{'chosen_poisson':rows[str(chosen)]['2025_test']['poisson_score'],
           'fixed3_poisson':rows['3.0']['2025_test']['poisson_score'],
           'chosen_mae':rows[str(chosen)]['2025_test']['mae'],
           'fixed3_mae':rows['3.0']['2025_test']['mae']},
       'runtime_seconds':round(time.monotonic()-started,2),
       'disclaimer':'2025 is not independently untouched; never select after seeing 2025 and report the same outcomes as an independent test. Any future rollout must preserve archived original forecasts.'}

def main():
    root=Path(__file__).resolve().parents[1]
    report=study(root)
    out=root/'outputs/v8_validation/recency_half_life_review.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'selected_using_2024_only':report['selected_using_2024_only'],
       'validation_and_test':report['rows']},indent=2))
if __name__=='__main__':main()
