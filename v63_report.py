#!/usr/bin/env python3
"""Display MLB October scoring research context, not a betting recommendation."""
from v63_postseason import load_years,retrospective_season_diagnostics,context_for_game
import json

def main():
    print('Imported league-level rows:',len(load_years()))
    print('RUNS PER GAME are PER TEAM, not combined (double for two equal teams).')
    print('Annual-score leave-one-year-out diagnostic (not game-level validation):')
    for x in retrospective_season_diagnostics():print(x)
    for day in ('2026-10-10','2026-10-11','2026-10-12','2026-10-13'):
        ctx=context_for_game(day,'P')
        print(day,'postseason multiplier',round(ctx['factor'],4),
              'used 2026 snapshot?',ctx['current_2026_snapshot_used'])
    print('Data source: user-supplied CSV; 2022-26 runs/team-game series cross-checked against CBS Sports (Oct 11, 2026).')
    print('2026 relief, HR and velocity columns are provisional audit inputs, not additional run multipliers.')
    print('This scenario is NOT an independently validated betting edge.')
if __name__=='__main__':main()
