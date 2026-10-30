# Project portfolio / recruiter guide — October 2026

**Project:** MLB Forecast Lab — Automated Baseball Forecasting, Cloud Pipeline and Auditable Evaluation

**Tech stack:** Python 3.12, NumPy, Pandas, scikit-learn (Poisson regression), GitHub Actions, GitHub Pages, JSON/CSV, MLB data endpoints and Retrosheet.

**Live example:** [2026 historical dashboard](https://andys3-design.github.io/MLB-Postseason-Forecast-Model/) · [Source and README](../README.md) · [2026 official results](FINAL_2026_RESULTS.md).

## Ready-to-use résumé bullets

- **Developed** an end-to-end Python MLB analytics system using historical data, recency-weighted Poisson scoring models, an Elo baseline and approximately **12,000 simulations per forecast** to estimate game winners, score distributions and game totals.
- **Automated** data refresh, forecast generation, test execution and GitHub Pages publishing with GitHub Actions, building a mobile-friendly public dashboard and automated official-result reconciliation.
- **Engineered** pre-first-pitch data integrity safeguards: immutable original predictions, first-commit provenance verification, append-only official settlement, identity checks, concurrency-safe publication and regression-tested failure handling.
- **Designed** a retrospective and prospective model-evaluation framework that retains missed predictions in the complete denominator and evaluates same-game win accuracy, Brier scores, run-total MAE, model vs Elo comparisons and actual simulated winner-plus-Over joint probabilities.
- **Documented model limitations transparently:** the 2026 monitored cohort finished at **5/11 correct overall (45.5%)**, with nine valid frozen pregame originals; on nine matched games Elo achieved 8/9 correct and the primary model 5/9.

For an entry-level tech, information security or analytics résumé, prioritize the first three bullets, adding the evaluation bullet if space permits. Do not claim that a baseball forecasting project is an intrusion-detection or professional cybersecurity system.

## Short recruiter description

> Built and deployed a reproducible MLB prediction and analytics application using Python and cloud automation. The system transforms baseball data into probabilistic forecasts, publishes a public dashboard, and independently audits immutable pregame predictions against official outcomes. The project demonstrates Python programming, CI/CD, data pipeline reliability, scientific evaluation and data-integrity engineering. I also documented what did **not** work, including the distinction between historical backtests and genuine future-game forecasting accuracy.

## Honest technical highlights

| Area | Demonstrable implementation |
|---|---|
| Modeling | Recency-weighted Poisson score regression; fixed Elo; score-distribution simulations |
| Data | Earlier-date features; official game schedule / final data, historical logs, missing-data quality flags |
| Cloud and DevOps | GitHub Actions CI, data jobs, manual execution, static GitHub Pages deployment |
| Data integrity | Immutable originals, UTC first-pitch checks, Git first-commit audit, SHA-protected official settlement |
| Software reliability | Recovery guard, safe concurrent first-writer-wins forecast persistence, regression suites |
| Research | Historical 30-game replay; complete 11-game monitored prospective cohort; same-game Brier and McNemar |
| Responsible reporting | No 90% accuracy claim; missing predictions count against cohort; no artificial probabilities |

## How to demonstrate in an interview

1. Show a stored pregame JSON prediction and the original GitHub commit timestamp, followed by its official final settlement.
2. Trace the game data from `cloud/worker.py` through feature and run-rate models, the simulated score probability grid, and `site/data.json`.
3. Open the GitHub Actions history showing CI and a successful Pages deployment; explain why the 2026 recurring schedules have been paused.
4. Use the [final scorecard](FINAL_2026_RESULTS.md) to explain missing predictions vs matched-game probability scoring. Explain why 5/11 is the proper complete-cohort number, not 5/9.
5. Contrast the original model, Elo and V23 results and explain why a small sample and p = 0.25 did not justify changing production weights.
6. Discuss append-only settlement, optimistic concurrency and first-writer-wins as examples of auditability, change control and data integrity.

## Portfolio presentation checklist

- [ ] Show the [GitHub repository](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model).
- [ ] Show a screenshot of the public historical dashboard, preferably with the original timestamp visible.
- [ ] Show at least one [passing CI run](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/41058727480).
- [ ] Link the [final results and limitations](FINAL_2026_RESULTS.md).
- [ ] Highlight responsibilities, tooling and engineering lessons ahead of raw sports prediction claims.

**Interview position:** This is a strong *software engineering and data-integrity* case study, not proof of a betting strategy, a stable 90%-accuracy model, or a specialist security product. The 2026 season is archived and GitHub forecast cron is paused. Code, test results, forecasts and research history remain accessible for review.
