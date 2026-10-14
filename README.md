# MLB Forecast Lab

**Cloud-hosted, baseball-only MLB forecasting and model-evaluation project.**

[Live forecast dashboard](https://andys3-design.github.io/MLB_Backtest_Expanded_2026_Postseason_Markets/) · [GitHub Actions runs](https://github.com/AndyS3-design/MLB_Backtest_Expanded_2026_Postseason_Markets/actions) · [Documentation index](docs/README.md)

MLB Forecast Lab is a Python research project that ingests historical and current MLB data, builds run-scoring and win-probability forecasts, simulates possible scores, and saves **time-stamped predictions before first pitch**. A GitHub Actions workflow runs independently of a personal computer and publishes a phone-friendly GitHub Pages site.

> **Status:** Working public deployment; prospective accuracy evaluation is in progress. The model is experimental. More historical data or a successful individual prediction does **not** establish improved forecasting accuracy.

## What it does

- **Baseball-only inputs:** Retrosheet historical game logs, official MLB game results and pregame information; no sportsbook odds or prediction-market prices in the deployed forecasting pipeline.
- **Historical training:** Supports 2016–2025 regular-season records with recency-weighted Poisson regression (roughly a 3-year weighting half-life). Training coverage is recorded for each new forecast.
- **Game-specific context:** Previous team performance, starting-pitcher history, bullpen data, postseason run environment, and available lineup information. Missing or experimental inputs are identified instead of silently invented.
- **Simulation:** Runs 12,000 simulated games per cloud forecast, publishing expected runs, a representative projected score, winner probabilities and a distribution of possible totals.
- **Pregame integrity:** Saves the original forecast with its actual creation time and model version. One-off revisions, when authorized before first pitch, are stored separately; the original is never overwritten.
- **Independent schedule cross-check (V10):** Reconciles a rolling seven-day sample of official MLB final games against imported results and frozen original forecasts, flagging missing imports that V9 alone cannot detect.
- **Live forecast-capture monitoring (V9):** Counts imported completed games that had a genuine original pre-first-pitch forecast, separately flags missed/late predictions, and records settlement status. Starts October 14, 2026; zero completed games is shown as not measurable, not as success.
- **Prospective research comparisons:** Future eligible games can also save separately timestamped alternative forecasts, to test additional pitcher and postseason-scoring corrections without changing the primary prediction.
- **Automated publishing and evaluation:** Uses GitHub Actions and GitHub Pages; later attaches official finals and calculates error metrics against an Elo baseline.

## Quick start

The maintained cloud application is inside [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/), **not** the older root-level `dashboard.py` or `index.html`.

1. To **view** forecasts, open the [live dashboard](https://andys3-design.github.io/MLB_Backtest_Expanded_2026_Postseason_Markets/).
2. To **run the cloud workflow**, go to [Actions](https://github.com/AndyS3-design/MLB_Backtest_Expanded_2026_Postseason_Markets/actions) → **MLB Forecast Lab — game-time forecasts** → **Run workflow** on `master`.
3. To **test locally** from the repository root (Python 3.12 recommended):

   ```powershell
   cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
   py -m pip install -r requirements.txt
   py -m unittest cloud.test_cloud cloud.test_v7 cloud.test_starter_backfill cloud.test_revision -q
   py -m cloud.worker render
   ```

   The render command regenerates the local static site from existing forecast records; it does not generate a new pregame forecast. Run networked data refreshes only in a controlled copy of the repository.

See [deployment and operations](docs/OPERATIONS.md) for the complete GitHub setup, schedule, debugging and recovery process.

## Repository map

| Path | Purpose |
|---|---|
| [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/) | Forecast worker, first-pitch checks, data refresh and historical backfill |
| [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/v4_matchup_core.py`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/v4_matchup_core.py) | Run-model training and forecasting |
| [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/v4_workflow.py`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/v4_workflow.py) | End-to-end baseball matchup simulation inputs |
| [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/site/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/site/) | Static website published by GitHub Pages |
| [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/) | Saved originals, any separately labeled revisions, run status |
| [`.github/workflows/mlb-cloud.yml`](.github/workflows/mlb-cloud.yml) | Cloud schedule, tests, forecast/persist job and Pages deployment |
| [`docs/`](docs/) | Maintained architecture, model, validation, operations and portfolio documentation |
| Root-level research scripts and V1–V7 install guides | **Legacy research/history.** Preserved for reproducibility; not the entry point for the deployed cloud app |

**Scope note:** Older, unused market-analysis scripts remain at the repository root from earlier experiments. They are **not imported by the maintained cloud workflow**. They have not been deleted because doing so requires a separate dependency and regression audit.

## How to interpret the output

- **Expected total runs** is the average over the simulated games.
- **Illustrative score** is one discrete scoreline selected from the simulated distribution. It is not a claim that exact score is highly likely.
- **Win probability** is an estimate, not a guarantee. A 55% favorite still loses frequently.
- **Data quality** flags identify missing pitcher history, lineups or other context.
- **Original vs updated pregame:** Both have their own timestamps. Only original forecasts enter the primary prospective performance summary, avoiding double-counting.

## Documentation

Start with the [documentation index](docs/README.md); recommended reading: [architecture](docs/ARCHITECTURE.md), [model and data](docs/MODEL_AND_DATA.md), [validation](docs/VALIDATION.md), [operations](docs/OPERATIONS.md), [project status and roadmap](docs/ROADMAP.md), and [resume/portfolio guide](docs/PORTFOLIO.md).

## Evidence and accuracy status

The [V8 measured-results report](docs/V8_RESULTS.md) documents the complete **28-game 2026 postseason retrospective replay** (64.3% winners correct, but a total-run MAE of 2.713 and worse run-error metrics than a simple historical playoff-average baseline) and a **2022–2025 chronological test** on 19,404 team-game observations. These are exploratory studies, **not** evidence of guaranteed or independently verified live accuracy.

The current dashboard includes **prospective-only accuracy and data-quality tracking**. New pitcher and bullpen research diagnostics do not automatically alter forecast probabilities.

## Data credit and limitations

Historical baseball information was obtained free of charge from, and is copyrighted by, **Retrosheet**. See [Retrosheet](https://www.retrosheet.org/) for information and attribution. Current schedules, game results and boxscores are obtained from official MLB data endpoints. Coverage and availability can change.

This repository is an independent educational project, not affiliated with or endorsed by MLB or Retrosheet. It does not establish betting profitability or guaranteed prediction accuracy. The project does not include a license granting others broad reuse rights; contact the repository owner before reusing substantial source code.
