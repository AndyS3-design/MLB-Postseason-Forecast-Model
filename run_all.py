#!/usr/bin/env python3
"""One command to regenerate the expanded validation from locally available data.
Use ingest_mlb.py first if you have Internet and want current 2026 data.
"""
import json
import subprocess
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
COMMANDS=[['-m','unittest','discover','-q'],['extended_eval.py'],['playoff_diagnostics.py'],
          ['market_baseline.py'],['market_backtest.py'],['matchup_model.py'],['score_backtest.py']]

def main():
    for args in COMMANDS:
        print('RUN:',sys.executable,*args,flush=True)
        subprocess.run([sys.executable,*args],cwd=HERE,check=True,
                       stdout=None if args[:2]==['-m','unittest'] else subprocess.DEVNULL)
    res=json.loads((HERE/'outputs'/'extended_metrics.json').read_text())
    print('\nCOMPLETE:')
    for n,m in res['splits'].items():
        print(f"  {n}: {m['n']} games, "+
              (f"Elo accuracy {m['elo_winner']['accuracy']:.1%}" if m['n'] else 'NOT AVAILABLE'))
    odds=json.loads((HERE/'outputs'/'market_backtest.json').read_text())
    print('  Kalshi prices:',odds['status'])
    advanced_path=HERE/'outputs'/'matchup_model_metrics.json'
    if advanced_path.exists():
        advanced=json.loads(advanced_path.read_text())
        print('  EXPANDED MATCHUP PROTOTYPE (not promoted over Elo):')
        for split,data in advanced.get('splits',{}).items():
            if not data.get('n'):continue
            print(f"    {split}: {data['n']} games, Elo Brier {data['elo']['brier']:.5f}, "
                  f"expanded Brier {data['expanded']['brier']:.5f}")
        print('  Actual detailed pitching rows:',advanced.get('details_rows_applied',0))
    score_path=HERE/'outputs'/'score_metrics_2025.json'
    if score_path.exists():
        sm=json.loads(score_path.read_text())
        print(f"  EXPERIMENTAL SCORES: {sm['n']} held-out games, run MAE/model {sm['mean_run_absolute_error_per_team']['score_model']:.3f} vs baseline {sm['mean_run_absolute_error_per_team']['constant_team_run_baseline']:.3f}")
    print('  Model improvement and pricing claims require independent validation; see MODEL_CARD.md')
if __name__=='__main__':main()
