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

## V8.1 prospective A/B research (implemented, awaiting future results)

- [x] Save research variants separately before first pitch; preserve frozen original prediction.
- [x] Compare no additional starter correction and (postseason only) no postseason scoring context.
- [x] Show paired accuracy metrics in the cloud dashboard when new official finals are available.
- [ ] Collect a meaningful new, independent sample and evaluate uncertainty before selecting a better production formula.

Methodology: [Prospective experiments](PROSPECTIVE_EXPERIMENTS.md).

## V9 prospective reliability (deployed after tests)

- [x] Track imported completed games **without** original timely forecasts, beginning October 14, 2026.
- [x] Separate pending official settlement from missing original predictions.
- [x] Show capture rate and missed-game explanations on the public dashboard.
- [x] Add independent GitHub Actions health job for approaching-game IDs without a saved, timely original prediction.
- [ ] Accumulate enough future imported completed games to estimate model accuracy and operational capture reliability; do not advertise success with zero or tiny samples.

## V10 official schedule reconciliation (merged, production verification pending)

- [x] Implement a separate rolling seven-day official final-game denominator, distinct from imported-only V9 coverage.
- [x] Detect games with missing result imports, absent/late original forecasts and score/date mismatches without fabricating late predictions.
- [x] Wire daily maintenance audit and public dashboard status, with explicit stale/unavailable status and automated mock-schedule regression tests.
- [ ] Confirm GitHub Actions tests on the V10 pull request and subsequent deployed full maintenance audit; continue collecting untouched prospective games.

Details: [V10 independent MLB schedule audit](OFFICIAL_SCHEDULE_AUDIT.md).

## V12 two-stage game-day publication

- [x] Gate an early preliminary prediction from 10 AM Eastern on game day, only when at least 45 minutes remain before first pitch.
- [x] Keep the late final forecast in the original locked JSON and preserve preliminary separately without overwrites or backdating.
- [x] Show both stages and preliminary-vs-final score changes on the dashboard; restrict primary Brier, MAE and Elo metrics to final originals.
- [x] Add prospective paired evaluation and scheduling/immutability regression tests.
- [ ] Verify CI and the first live two-stage prediction pair; future two-stage capture depends on GitHub Actions schedule reliability.

Method and limitations: [two-stage forecasts](TWO_STAGE_FORECASTS.md).
