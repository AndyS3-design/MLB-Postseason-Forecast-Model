# MLB Prediction Lab V4 — Windows setup

This is an **add-on** for the MLB Prediction Lab project already running in Visual Studio / Developer PowerShell.

## Install without losing your data

1. Stop Streamlit in the Developer PowerShell window using **Ctrl+C**.
2. Make a backup of your current `MLB_Backtest_Expanded_2026_Postseason_Markets` folder.
3. Extract `MLB_Prediction_Lab_V4_DEEP_MATCHUPS_ADDON.zip`.
4. Copy the `v4_*.py` modules, `test_v4_research.py`, and **merge** the `pages/` folder into your existing project directory (next to `dashboard.py` and `run_all.py`).
5. **Do not remove or replace your `data/`, `outputs/` or existing `pages/` directories.**

In the original project directory, run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -q
py v4_validate.py --as-of 2026-10-13
py -m streamlit run dashboard.py
```

Open **Deep Matchup Lab** in the Streamlit navigation. It runs alongside the original forecast, prospective tracking, and live scoreboard pages.

## How to predict games

1. Select a **future official game** and confirm the starter IDs from the schedule.
2. Before **scheduled** first pitch, click **Load confirmed pregame lineups & bullpen roster from MLB**. If lineups have not been released, their adjustment stays **neutral** and a coverage warning appears. The fetch is blocked once scheduled start passes.
3. Optional: enable the **historical home park proxy** only if you're certain the game is at the same home venue; or type a **manual park factor**. Weather inputs are optional **unvalidated scenarios**, not a calibrated weather forecast.
4. Choose 30,000–100,000 simulations and click **Simulate this matchup**. Probabilities for winner, totals, spread and final scores are all computed from the same simulated outcomes.
5. Review the **coverage warnings** and **Elo comparison**. In particular, the pitch-by-pitch and hitter-handedness models are only proxies, not independently fitted Statcast matchup models.
6. Optionally input an actual **Kalshi BUY YES ask** and fee from the order ticket to check model break-even arithmetic. These are **not fetched automatically**, nor are orders placed.
7. **Before** first pitch, you can freeze exactly one forecast per official game to `outputs/v4_pregame_forecasts.jsonl`. This local log does not guarantee an exchange quote or a profitable strategy.

### Your two October 12 playoff games

If you're installing this after those games' scheduled start, the V4 page will allow **retrospective research** but will **not** call a new forecast or lineup snapshot a genuine pregame prediction. For fair future evaluation use the next unplayed game and freeze before its scheduled start.

## Data quality expectations

* Your prior `advanced_pitching_details.csv` and `pitcher_directory.csv` enable recent starter statistics.
* Previously imported `data/mlb_boxscores/*.json` from `import_mlb_boxscores.py` provide **historical** batter and individual reliever performance for the 2026 season. If the cache is missing, lineup/bullpen performance is neutral or team-level, with a warning. A recent fielding-error proxy is loaded from prior Retrosheet game logs and (when present) prior MLB box scores; it is NOT Outs Above Average or Defensive Runs Saved.
* Official lineup capture requires the public MLB game feed before first pitch. It may have **0 of 9** hitters if the starting lineup has not yet been announced; no imaginary starters are inserted.
* The pitcher-vs-lineup handedness adjustment is an **uncalibrated generic proxy**, not a claim to use xwOBA or pitch-level Statcast data.
* Park adjustment is a **venue/team-confounded 2023–24 run factor** unless manually provided. If a team moved parks, leave park disabled.
* Pretrained 2023–24 run model coefficients are selected using 2024 validation. The core run model can be backtested on 2025/2026; individual hitter/park/weather overlays and the exact inning simulation still require independent prospective testing.
* The modeled game winner is **not adjusted to match Elo**. Elo is presented as a separate, tested baseline; a difference between them is an important warning.
* Predictions should not be placed as real wagers solely because one or two tests improve.

## Testing, results, limitations

- Regression suite: `py -m unittest discover -q` (99 tests in this assembled development version).
- V4 core run validation: `py v4_validate.py --as-of 2026-10-13`.
- Results: `outputs/v4_model_validation.json`.
- Historical baseline comparison (2025 regular season only, 2,425 games): V4 average regulation team-run absolute error **2.4942**; original frozen 2023–24 run model **2.5146**; constant 4.5 runs **2.5515**. Historical repeated-model development means this is **not** a pristine, prospectively untouched holdout.
- With the provided older archive, 2026 data are not present. Your working Windows folder contains your current imports and will produce 2026 metrics after running the validator there.
- Modeling limitations: team-level Poisson regression; broad-handedness proxy; 9-inning gamma-Poisson approximation; extra-inning continuation approximation; no current injury feed, actual batting order until MLB releases it, detailed defensive alignments, pitch mix, pitch-by-pitch results, or executable exchange order-book data.

### Files installed

`v4_matchup_core.py`, `v4_sources.py`, `v4_defense.py`, `v4_park.py`, `v4_simulation.py`, `v4_workflow.py`, `v4_log.py`, `v4_validate.py`, `test_v4_research.py`, `pages/Deep_Matchup_Lab.py`.
