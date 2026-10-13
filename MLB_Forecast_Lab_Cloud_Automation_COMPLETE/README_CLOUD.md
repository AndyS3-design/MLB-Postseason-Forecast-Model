# MLB Forecast Lab — Maintained Cloud Edition

**This is the active Python forecasting application.** The root [README](../README.md) is the project front page, and the maintained documentation is in [../docs/](../docs/).

**Dashboard:** https://andys3-design.github.io/MLB_Backtest_Expanded_2026_Postseason_Markets/

The live pipeline is baseball-only. Historical league/team scoring, verified past starter starts, and official pregame MLB information feed the model. It does **not** use external sportsbook or prediction-market prices.

## Production entry points

- **GitHub Actions:** `../.github/workflows/mlb-cloud.yml`, `master` branch.
- **Schedule gate:** `cloud/preflight.py`; scheduled every five minutes (best effort), with daily full maintenance at 11:17 UTC.
- **Main worker:** `python -m cloud.worker run`; normal original forecast window is 8–30 minutes before first pitch.
- **Site:** `site/index.html` plus generated `site/data.json`, published using GitHub Pages.
- **Forecast history:** `cloud_records/predictions/`; separately labeled authorized pregame revisions in `cloud_records/revisions/`.
- **Test command:** `python -m unittest cloud.test_cloud cloud.test_v7 cloud.test_starter_backfill cloud.test_revision -q`.

GitHub may delay or skip scheduled checks. The system refuses to create a new pregame forecast after its time window has passed.

## Local setup

Use Python 3.12 for consistency with GitHub Actions:

```powershell
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
py -m pip install -r requirements.txt
py -m unittest cloud.test_cloud cloud.test_v7 cloud.test_starter_backfill cloud.test_revision -q
py -m cloud.worker render
```

`render` rebuilds the static website from saved JSON records without fetching new games. A networked `run` modifies imported baseball data and may commit new eligible forecasts in the corresponding GitHub workflow; run it only when you intend that behavior.

## Data and methods

- Retrosheet game logs support 2016–2025 historical training; the final 2026 model uses recency-weighted Poisson run predictions and past completed 2026 games as features, without treating 2026 game outcomes as model-training labels.
- The worker performs targeted MLB previous-start backfill before generating the game forecast.
- MLB schedule information provides game identity, timing and available official pregame personnel.
- Model adjustments for pitchers and postseason conditions remain experimental and must be prospectively validated.
- **12,000 simulations per cloud forecast** produce mean runs, winner probability and an illustrative discrete score.
- Official finals are attached later and the original forecast fields remain intact.

## Operational caution

There is no documented independently held-out result proving better accuracy from ten years of data versus a shorter history. The model is an educational research system. See [model methodology](../docs/MODEL_AND_DATA.md), [validation](../docs/VALIDATION.md), [operations](../docs/OPERATIONS.md) and [roadmap](../docs/ROADMAP.md).

**Historical credit:** Retrosheet information was obtained free of charge from and is copyrighted by Retrosheet (https://www.retrosheet.org/).
