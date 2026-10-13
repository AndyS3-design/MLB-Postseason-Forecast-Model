"""Measure repeat-load savings without changing trained coefficients or game forecasts."""
from pathlib import Path
import json,time
import numpy as np
from extended_eval import all_games
from v4_workflow import build_assets

def main():
    root=Path(__file__).resolve().parents[1]
    games=all_games(root/'data',True)
    start=time.perf_counter()
    a=build_assets(games,root)
    first=time.perf_counter()-start
    start=time.perf_counter()
    b=build_assets(games,root)
    second=time.perf_counter()-start
    fit1,fit2=a['fit'],b['fit']
    sample=np.ones((1,len(fit1.features)))
    predictions_equal=bool(np.allclose(fit1.pipeline.predict(sample),fit2.pipeline.predict(sample),rtol=0,atol=1e-12))
    if not predictions_equal:raise AssertionError('Cached model altered its prediction')
    report={'training_years':b['training_years'],'same_predictions':predictions_equal,
            'first_build_seconds':round(first,3),'second_build_seconds':round(second,3),
            'first_fit_cache':a['model_cache'],'second_fit_cache':b['model_cache'],
            'note':'Full asset rebuild includes feature enrichment; cached fit does not cache 2026 dynamic features.'}
    p=root/'outputs/v8_validation/cache_profile.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
