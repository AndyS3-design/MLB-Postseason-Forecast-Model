# MLB Prediction Lab v2 — four-part upgrade

This is an add-on to the *working* MLB Prediction Dashboard in Visual Studio's Developer PowerShell. **Your original `data/` folder is not overwritten by the add-on.**

## Install on Windows

1. **Make a backup** of `Downloads\MLB_Backtest_Expanded_2026_Postseason_Markets`.
2. Extract `MLB_Prediction_Lab_V2_ADDON.zip`.
3. Copy **all extracted files** into your existing `MLB_Backtest_Expanded_2026_Postseason_Markets` folder (where `run_all.py` lives). Choose *Replace* for source-code files such as `dashboard.py`, `backtest.py`, `forecast_engine.py`, `run_all.py`. **Do not remove or replace the existing `data/` folder**—this add-on doesn't contain it.
4. Open Developer PowerShell at your project directory and run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -q
py run_all.py
py -m streamlit run dashboard.py
```

Open `http://localhost:8501` if your browser does not launch. Leave the terminal open. `Ctrl+C` stops the app.

## What is available without additional downloads?

* **Default Elo winner probabilities** remain unchanged and remain the primary forecast.
* **Research matchup model:** prior team scoring, on-base/isolated-power proxies, relief-pitcher **counts**, team rest, managers' historical relief usage, starting-pitcher **starts** and *team runs conceded while the pitcher started*. These last statistics are proxies, **not pitcher ERA**.
* **Holdout comparison:** Brier, accuracy, log loss, calibration error and day-cluster bootstrap confidence intervals for 2025, plus 2026 if your local imported data are present.
* **Leakage and importer tests:** same-day and future outcomes cannot enter pregame feature values; missing actual pitcher stats are never invented.
* **Model disagreement alert:** if the experimental run-based winner probability differs by more than 15 percentage points from Elo, the app shows a warning.

**Very important:** The 2025 regular-season advanced-model Brier score was **0.24412** compared with **0.24406** for Elo on the available bundled files, so the expanded model is **not validated as superior**. Regular-season accuracy was 55.88% versus 55.13%, but betting value is not established. Both estimates will change slightly if your local project has more earlier postseason records than the bundled project.

## Add real 2023–2025 starting-pitcher and bullpen statistics (recommended)

Run **once** with internet access:

```powershell
py import_retrosheet_details.py --years 2023 2024 2025
```

This downloads year-specific CSV archives from `https://www.retrosheet.org/downloads/csvdownloads.html`, then writes:

- `data/advanced_pitching_details.csv` — **actual** starter outs, earned runs, strikeouts, walks, homers, bullpen outs and earned runs.
- `data/pitcher_directory.csv` — pitcher name, Retrosheet ID, and throwing hand when available.

The next `py run_all.py` retrains the **research-only** model and regenerates independent holdout metrics. The next time you reopen the Streamlit app, it will recognize the new files. Downloads may be large and take several minutes. If blocked by your network, you can manually download the season archives and place them in `data/retrosheet_detail_zips/` named `2023csvs.zip`, `2024csvs.zip`, `2025csvs.zip`, then run with `--offline`.

## Add **2026** actual pitching and bullpen results

First ensure your existing completed-game importer has run (your prior screenshots show that it has). Then, with internet access:

```powershell
py import_mlb_boxscores.py --start 2026-03-01 --through 2026-10-12 --workers 4
```

This reads previously imported 2026 game IDs and fetches actual game box scores and (when missing) MLB player throwing-hand metadata. Successful responses are saved in `data/mlb_boxscores/` and `data/mlb_people/`, so reruns can reuse cached data. **It may take several minutes**, depending on API availability, because a full season involves thousands of game box scores. The `--through` date is **exclusive**, preventing October 12 results from entering October 12 predictions. Missing/incomplete games are reported and skipped. Your existing results aren't overwritten by failed downloads.

For a quicker partial trial, use `--start 2026-09-01` to cover September and the early playoffs; however, this is **not full-season pitcher history**, so estimates should remain tentative.

Then run:

```powershell
py run_all.py
py -m streamlit run dashboard.py
```

You can view the expanded matchup forecast in **Game forecasts → Expanded matchup model — research comparison**. Use the **Prediction audit trail** and **Backtest & data quality** tabs to verify coverage before trusting a percentage.

## What the four upgrades do — and don't do

| Research component | Implemented | Important limitation |
|---|---|---|
| Starting pitchers | Prior starter starts, team runs allowed in their starts, and **actual** ERA/K/BB/IP once detailed box scores exist | Cannot infer actual ERA from team-score logs; probable pitcher may change before first pitch |
| Bullpens and October usage | Relief appearances over 3/7 days, actual recent bullpen outs/earned runs when available, team rest, lagged manager deployment/hook tendencies | This is **not** a full reliever-level leverage, injury, or availability model; postseason managerial effects are not causally calibrated |
| Offense/handedness | Recent team run production, approximate OBP and isolated power; team run output grouped by opposing **starter hand** when known | These are **not** real plate-appearance splits, wRC+, or confirmed lineups; relief pitchers affect full-game production |
| Validation/debugging | Independent 2025–2026 holdouts, Brier/log loss/accuracy/calibration, day-level uncertainty, leakage checks, Elo/run disagreement warnings | No historical executable Kalshi quote data; no proven betting profit |

## Extra notes

* Data imports and forecast inputs are strictly **older than the selected game date**. For dates before 2025, the expanded model refuses to show a “holdout” forecast because its parameters were trained through 2024.
* Historical Retrosheet pitchers have Retrosheet IDs; 2026 MLB pitchers use `MLB-<id>` IDs. The dashboard auto-fills IDs from official schedule if available. If an ID has **zero observed prior detailed starts**, it will be marked as such.
* The Streamlit app **does not place bets**, import your Kalshi balance, or obtain executable trading quotes. Prices remain manual; profitability is unverified.
* The optional 2026 importer uses MLB Stats API endpoints, and the Retrosheet importer uses official CSV archives. All actual game statistics are imported from those sources, never fabricated.

**Retrosheet attribution:** The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at 20 Sunset Rd., Newark, DE 19711.
