"""Data-only check for 2026 boxscore coverage; never changes project data."""
import csv
from pathlib import Path
from collections import Counter
from extended_eval import all_games
from matchup_model import loaded_details,enrich_games

root=Path(__file__).resolve().parent
folder=root/'data'
if not folder.exists():
    raise SystemExit('Missing data folder. Copy these .py files next to run_all.py, not inside data/.')
games=[g for g in all_games(folder,True) if g['year']==2026]
detail_path=folder/'advanced_pitching_details.csv'
if not detail_path.exists():
    raise SystemExit('No advanced_pitching_details.csv. Run import_mlb_boxscores.py first.')
with detail_path.open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f))
counts=Counter(r.get('date','')[:4] for r in rows)
details,hands,_=loaded_details(folder)
result,joined=enrich_games(games,details,hands)
matched_both=sum(bool(g.get('home_sp_outs') is not None and g.get('away_sp_outs') is not None) for g in result)
print('2026 game records:',len(games))
print('2026 detailed team-game rows in CSV:',counts['2026'])
print('2026 detailed team-game rows matched to schedule:',joined)
print('2026 games matched on BOTH sides:',matched_both)
print('Known pitcher throwing hands:',len(hands))
if counts['2026']==0:
    print('NEXT: py import_mlb_boxscores.py --start 2026-03-01 --through 2026-10-12 --workers 4')
elif joined==0:
    print('ERROR: 2026 detail CSV exists, but its game IDs or team codes still do not match. Please send the printed summary.')
else:
    print('SUCCESS: 2026 boxscore detail joins now work. Restart Streamlit and rerun the backtest.')
