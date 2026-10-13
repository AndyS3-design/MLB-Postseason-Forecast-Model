#!/usr/bin/env python3
"""Retrospective, leave-pregame-only game-level postseason context diagnostics.

The run model itself is trained on 2023-2024 REGULAR season. Postseason
adjustment uses prior completed season rates, except a dated pre-2026-LCS
snapshot that can affect Oct 12+ 2026 games. Historical 2025/2026 data were
already used during model design, so don't read this as untouched evaluation.
"""
from __future__ import annotations
import argparse,json
from collections import defaultdict
from datetime import date
from pathlib import Path
import numpy as np
from extended_eval import all_games
from v4_workflow import build_assets
from v4_matchup_core import historical_team_rows
from v63_postseason import context_for_game


def score(y,p):
    y=np.asarray(y,dtype=float);p=np.clip(np.asarray(p,dtype=float),0.3,16.0)
    return {'mae_runs_per_team':float(np.mean(np.abs(y-p))),
            'poisson_score_no_factorial':float(np.mean(p-y*np.log(p)))}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--as-of',default='2026-10-13')
    args=ap.parse_args();as_of=date.fromisoformat(args.as_of)
    root=Path(__file__).resolve().parent
    games=all_games(root/'data',True)
    assets=build_assets(games,root)
    df=historical_team_rows(assets['enriched'],assets['hands'])
    subset=df[(df['game_type']!='R') & (df['game_type']!='FORECAST') &
              (df['date']<as_of.isoformat()) & (df['year'].isin([2025,2026]))].copy()
    report={'cutoff_exclusive':as_of.isoformat(),'model_fit':'2023-2024 regular only',
            'status':'retrospective development diagnostics, NOT a prospective holdout',
            'groups':{}}
    if subset.empty:
        print('No eligible completed postseason games found; import MLB 2026 data if needed.');return
    fit=assets['fit']
    for season,year_rows in subset.groupby('year'):
        y=year_rows['runs_actual'].to_numpy(dtype=float)
        x=year_rows[fit.features].to_numpy(dtype=float)
        p=np.clip(np.asarray(fit.pipeline.predict(x),dtype=float),.3,16.)
        factors=np.asarray([context_for_game(day,gt,
                  root/'data'/'postseason_context_2022_2026.csv')['factor']
                   for day,gt in zip(year_rows['date'],year_rows['game_type'])],dtype=float)
        after=np.clip(p*factors,.3,16.)
        group={'team_game_rows':len(year_rows),'approximate_games':len(year_rows)//2,
               'rate_without_postseason':score(y,p),
               'rate_with_postseason':score(y,after),
               'mean_factor':float(np.mean(factors)),
               'snapshot_rows_2026':int(sum(date.fromisoformat(d)>=date(2026,10,12)
                 for d in year_rows['date'])) if season==2026 else 0}
        group['mae_improvement_positive_is_better']=(
            group['rate_without_postseason']['mae_runs_per_team']-
            group['rate_with_postseason']['mae_runs_per_team'])
        report['groups'][str(season)]=group
        print(season,':',group)
    path=root/'outputs'/'v63_postseason_validation.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print('Saved',path)
    print('WARNING: 2025/2026 were previously used during development. A favorable result here does not establish better future betting predictions.')

if __name__=='__main__':main()
