"""Retrospective 2025 comparison: 2023–24 fit vs 2016–24 fit.

This is a research benchmark, NOT untouched validation. 2025 outcomes have
already been used in earlier development, and neither model includes 2025
outcomes in this comparison's training. The deployed 2026 model can then be
trained through 2025 after this report without leaking 2026 results.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games
from v4_defense import add_fielding_errors
from v4_matchup_core import historical_team_rows,train_frozen_run_model,predict_rates,_poisson_loss

def compare(root):
    root=Path(root);games=all_games(root/'data',True)
    hist=[g for g in games if g['year']<=2025]
    years=sorted(set(g['year'] for g in hist if g['year']<=2025 and g['year']>=2016))
    if years!=list(range(2016,2026)):
        return {'status':'insufficient_history','available_years':years,
                'missing_years':sorted(set(range(2016,2026))-set(years)),
                'note':'The model will report its actual training coverage; no ten-year claim yet.'}
    details,hands,_=loaded_details(root/'data')
    enriched,_=enrich_games(hist,details,hands)
    enriched,_=add_fielding_errors(enriched,root/'data')
    frame=historical_team_rows(enriched,hands)
    test=frame[(frame.year==2025)&(frame.game_type=='R')]
    results={'status':'retrospective_exploratory','test_year':2025,'test_team_games':len(test),
             'policy':'2025 excluded from both fitted comparisons. New prospective 2026 games remain decisive.'}
    y=test.runs_actual.to_numpy(dtype=float)
    for label,start in (('three_years_training_2023_24',2023),('nine_years_training_2016_24',2016)):
        fit=train_frozen_run_model(frame[(frame.year>=start)&(frame.year<=2024)])
        mu=np.asarray(predict_rates(fit,test))
        results[label]={'training_years':fit.training_years,
                        'mae_per_team':float(np.mean(np.abs(mu-y))),
                        'poisson_score_lower_is_better':_poisson_loss(y,mu),
                        'validation_2024_poisson_score':fit.validation_poisson_deviance}
    left=results['three_years_training_2023_24'];right=results['nine_years_training_2016_24']
    results['ten_year_history_model_better_on_2025_poisson']=right['poisson_score_lower_is_better']<left['poisson_score_lower_is_better']
    return results

def main():
    root=Path(__file__).resolve().parents[1]
    results=compare(root)
    out=root/'outputs'/'v7_history_benchmark.json'
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
