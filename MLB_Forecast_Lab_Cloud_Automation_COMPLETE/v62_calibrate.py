#!/usr/bin/env python3
"""Run on user's imported 2023-25 Retrosheet pitching data; tune 2024 only."""
from __future__ import annotations
import json
from pathlib import Path
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games
from v4_matchup_core import historical_team_rows
from v62_pitching import calibrate_from_rows


def main():
    root=Path(__file__).resolve().parent
    data=root/'data'
    details,hands,_=loaded_details(data)
    if len(details)<5000:raise SystemExit('Detailed pitching records missing. Run: py import_retrosheet_details.py --years 2023 2024 2025')
    games=all_games(data,False)
    enriched,n=enrich_games(games,details,hands)
    frame=historical_team_rows(enriched,hands)
    report=calibrate_from_rows(frame)
    report['detailed_team_game_rows_matched']=n
    path=root/'outputs'/'v62_pitcher_calibration.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Starter adjustment calibration completed; 2024 chose weight',report['selected_weight'])
    print('2024 detailed starter feature coverage:',report['observed_starter_coverage_2024'])
    print('2025 diagnostic games:',report['holdout_2025']['n_games'])
    for key,v in report['holdout_2025'].items():
        if isinstance(v,dict):print(key,'MAE',round(v['mae'],4),'Poisson score',round(v['mean_poisson_log_loss_omitting_factorial'],5))
    print('Saved:',path)
    if report['selected_weight']==0:
        print('WARNING: 2024 validation did not justify a nonzero starter adjustment. No new effect will be applied automatically.')
    else:
        print('NOTE: This weight was selected with 2024 data; check 2025 results and future games before trusting it.')

if __name__=='__main__':main()
