# Model Card — MLB Prediction Lab v2

**Status:** Research prototype / not a validated profitable betting system. The Elo baseline is the primary displayed win model. The expanded matchup model is an experimental comparator, **not deployed to Kalshi price checks**.

## What changed

- Starting pitchers: chronological (lagged) starter appearances and team runs conceded while the starter was used. When separate **actual** pitching rows are imported, lagged starter outs/earned runs/strikeouts/walks are used. The importer never calls team runs a pitcher's ERA.
- Bullpens: lagged 3-day and 7-day relief-pitcher counts (Retrosheet game logs) and, when supplied, actual recent bullpen outs and bullpen earned runs. These are fatigue proxies, not full availability or leverage estimates.
- Offensive matchups: recent runs, home/away approximation, hit/walk/HBP-based OBP proxy and extra-base-hit-based ISO. If starters' throwing hands are available from Retrosheet/MLB metadata, full-team scoring against left/right *starting pitchers* enters as a smoothed proxy; this is NOT a true batter-vs-pitcher-hand stat such as wRC+.
- Managers: lagged historical average pitcher changes and mean starter innings when boxscore detail exists. Postseason strategy effects have not been independently learned or shown to improve holdouts.
- Validation: LogisticRegression(C selected using only 2024 validation after training on 2023; coefficients refitted to 2023–24). 2025 and 2026 are kept out of fit/tuning. Actual day-by-day forecasts are updated from *strictly earlier* games. No future same-day scores enter features. Report probability calibration and uncertainty intervals from resampling entire game dates.

## Results from bundled data (optional advanced detail absent)

| Test split | N | Elo winner accuracy | Expanded winner accuracy | Elo Brier | Expanded Brier |
|---|---:|---:|---:|---:|---:|
| 2025 regular season | 2425 | 55.13% | 55.88% | 0.24406 | 0.24412 |
| 2025 postseason | 47 | 48.94% | 55.32% | 0.24805 | 0.24563 |

Brier improvement (Elo minus expanded) on 2025 regular season: **−0.00006**, day-cluster bootstrap 95% interval **[−0.00169, +0.00162]**. Postseason difference: **+0.00243**, 95% interval **[−0.00477, +0.01044]**. Neither result demonstrates dependable superiority. Accuracy alone is inadequate, especially if market prices are unfavorable.

2026 records were not available to the build environment. **Your local 2026 imports are preserved in the existing project** and the new validation script will report 2026 results on your machine. The full ZIP without those files will report an unavailable 2026 holdout until it imports games.

The expanded model requires historical detailed pitching files before displaying pitcher-specific earned-run-rate and strikeout adjustments; without them these inputs are neutral and coverage counters equal zero. Details may change the fitted model and therefore require rerunning tests and validating anew.

## Do not infer

- That more features necessarily produce greater predictive accuracy.
- That 26 playoff games can establish a postseason edge.
- That scoreline-implied odds guarantee a profitable trade.
- That a probable pitcher displayed in the schedule is the actual starter.
- That bullpen-pitcher count is a rigorous measure of fatigue, or that manager tendencies are causal.
- That historical end-of-game data can safely be used in a prediction for the SAME game date.

## Reproducibility

Run `py run_all.py` and read `outputs/matchup_model_metrics.json` and `outputs/matchup_model_predictions.csv`. Exact prior-season availability and optional detail file inputs determine the actual model results. Run `py -m unittest discover -q` for leakage and import tests.

**Retrosheet attribution:** The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at 20 Sunset Rd., Newark, DE 19711.
