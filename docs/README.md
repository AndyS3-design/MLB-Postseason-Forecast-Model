# MLB Forecast Lab — Documentation

These are the **maintained** documents for the baseball-only GitHub Actions + GitHub Pages version of the project. Earlier root-level installation guides describe previous releases and are kept as historical development artifacts.

| Document | What you'll learn |
|---|---|
| [Architecture](ARCHITECTURE.md) | Data flow, worker, simulation, immutable records and static dashboard |
| [Model and data](MODEL_AND_DATA.md) | Historical inputs, training, pitching, probabilities and data provenance |
| [V17 reliability and validation](RELIABILITY_AND_VALIDATION_V17.md) | Final-window safety, full-PMF prospective calibration, postseason dispersion study and shadow experiments |
| [V14 score and total odds](SCORE_AND_TOTAL_ODDS_V14.md) | Why exact-score mode differs from mean expected runs and 3.5–6.5 over/under odds |
| [V13 official postseason scoring](POSTSEASON_SCORING_V13.md) | MLB 2020–2026 actual runs, chronological adjustment selection, genuine-simulation checks and scoreline presentation |
| [V8 measured evidence](V8_RESULTS.md) | Complete 2026 playoff replay, multi-year run-model validation and cache benchmark |
| [V9 pregame capture monitoring](V9_PROSPECTIVE_MONITOR.md) | Detect missed games, validate timestamps and separate imported outcomes from pending settlement |
| [Prospective experiments](PROSPECTIVE_EXPERIMENTS.md) | Before-first-pitch shadow forecasts, paired scoring and decision rules |
| [Validation](VALIDATION.md) | Leakage prevention, holdouts, uncertainty and honest performance claims |
| [Operations](OPERATIONS.md) | How to run, deploy, debug and safely recover the hosted workflow |
| [Roadmap](ROADMAP.md) | Verified current scope, remaining issues and technical priorities |
| [Resume and portfolio](PORTFOLIO.md) | Evidence-based résumé bullets, skills and interview talking points |

**Maintained source of truth:** `../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/` and `../.github/workflows/mlb-cloud.yml`. The root `README.md` is the project front page.

**Documentation policy:** Describe implemented functionality and measured results separately. Do not promote historical research or one-off examples into claims of demonstrated future accuracy.
