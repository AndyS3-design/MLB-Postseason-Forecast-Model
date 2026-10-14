# Project status and roadmap

_Last reviewed: October 13, 2026. This is a technical checklist, not a performance claim._

## Implemented and verifiable in this repository

- Python baseball forecasting pipeline and score simulation.
- Retrosheet 2016–2025 historical-game support with recency-weighted run-model fitting.
- Official MLB schedule, completed-game import and targeted prior-starter boxscore enrichment.
- Starting-pitcher calibration and postseason-context research layers.
- Cloud schedule gate, UTC pregame cutoff checks and GitHub Pages publication.
- Original forecast JSON records with explicit one-off pregame revision handling.
- Official result settlement and metrics including Brier scores, MAE and an Elo comparison.
- Automated tests covering game-window eligibility, backfill identity checks and revision integrity.

Example: the October 13, 2026 Cleveland–Tampa Bay revised pregame record reports all ten training seasons and eight verified prior starts per listed pitcher. This documents input availability, not a proven performance improvement.

## Next priorities (ordered)

1. **Prospective evidence:** Accumulate forward-looking predictions without retuning to their known finals. Monitor missing forecast rate, date coverage and baseline performance.
2. **Time-window reliability:** Measure how often GitHub scheduling actually captures the intended 8–30-minute window; add meaningful alerts if runs fail or the site becomes stale.
3. **Historical comparison:** Execute and document the real 2025 shorter-versus-longer-history benchmark (the included comparison script exists, but no final benchmark report is currently committed).
4. **Pitcher/bullpen validation:** Compare with/without starter adjustment on forward-looking games, avoiding double-counting team pitching and starter effects.
5. **Data provenance:** Record more explicit source and fetch timestamps for announced starters, lineup changes and park conditions; retain missing-value explanations.
6. **Forecast calibration:** Publish reliability plots, confidence intervals and baseline comparisons after a sufficiently informative number of settled games.
7. **Repository maintenance:** After verifying imports/tests, consider moving legacy code to an archival branch or separating it into a research repository; do not reorganize production paths while the workflow depends on them.
8. **Reproducibility:** Introduce dependency lockfiles, versioned data manifests and automated document/site validation without committing sensitive secrets.

## What is deliberately *not* claimed

- A guaranteed forecast 20 minutes before every game.
- Improved accuracy solely because 2016–2025 seasons are present.
- A validated win-rate advantage or strong probabilities based on one playoff series.
- Independent incremental value from all lineup, park, weather or bullpen overlays.
- Sportsbook or prediction-market-driven predictions, betting returns, or endorsement by MLB.

## Change-management rule

Any algorithm change prompted by observing a game's outcome should be logged as development and evaluated on later, untouched games. Preserve the original saved forecast as the baseline for primary prospective scoring.

## V8 completed research and infrastructure

- [x] Replayed 28 completed 2026 postseason games with strict earlier-date feature cutoffs; report and game CSV saved.
- [x] Compared model vs Elo and prior-season playoff baselines; scoring overprediction identified.
- [x] Ran 2022–2025 regular-season chronological run-model evaluation and feature ablations.
- [x] Added content-addressed cache for frozen historical Poisson fit, preserving matchup-specific feature refresh.
- [x] Added prospective model-health/coverage reporting and pregame bullpen workload shadow metrics.
- [ ] Build a new postseason-run adjustment only if calibrated on *separate earlier seasons* and tested prospectively.
- [ ] Gather a substantial untouched cohort of live original forecasts; evaluate calibration and uncertainty.

See [V8 measured evidence](V8_RESULTS.md).
