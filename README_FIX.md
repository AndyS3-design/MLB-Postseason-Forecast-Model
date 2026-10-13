# MLB Prediction Lab v2 — Retrosheet Doubleheader Fix

## Why this happened
On April 18, 2023, Philadelphia (PHI) visited the Chicago White Sox (CHA) twice.
The original importer stored pitching records keyed only on date + home + away + side.
Game 1 and game 2 consequently collided. **Both games are valid.**

## What changed
- `import_retrosheet_details.py` preserves Retrosheet's `gid` and game `number` for each pitching record.
- `matchup_model.py` matches those records against Retrosheet game logs by **game number**, or MLB imported games by **game ID**; it doesn't attach ambiguous unnumbered rows to doubleheaders.
- `import_mlb_boxscores.py` preserves MLB game IDs when merging detailed records so 2026 doubleheaders don't collide either.
- `test_doubleheader_fix.py` adds four regression tests for doubleheaders and older single-game records.

## Windows Visual Studio Developer PowerShell
1. Stop the dashboard (Ctrl+C in its terminal) and make a backup of your project folder.
2. Extract the attached ZIP. Copy the four `.py` files into your existing `MLB_Backtest_Expanded_2026_Postseason_Markets` directory, overwriting **the three existing files** when prompted. Do NOT replace your `data` folder.
3. Open Developer PowerShell in your project folder and run:

```powershell
py -m unittest discover -q
py import_retrosheet_details.py --years 2023 2024 2025
py run_all.py
py -m streamlit run dashboard.py
```

The importer's previously downloaded `2023csvs.zip`, `2024csvs.zip`, and `2025csvs.zip` are reused from `data/retrosheet_detail_zips`. No further historical-download step should be needed.

## Data safety
This fix only changes how pitching details are matched. It does **not** erase your 2026 regular-season records or make the research model a validated betting system. The old importer failed before writing the 2023–25 pitching-details output, so rerunning it is needed for those details to appear.

## Tests
The updated project passed 38 tests, including four new regression tests for a 2023 doubleheader and 2026 game-ID behavior.
