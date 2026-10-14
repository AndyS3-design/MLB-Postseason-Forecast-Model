# V17 — Reliability, scoring evidence, audited context and portfolio-quality validation

This release prioritizes **reproducibility and honest forecasting** over changing a model coefficient until there is independent evidence.

## 1. Earlier wakeups, unchanged first-pitch lock

GitHub's cron runner is best-effort, not a guaranteed scheduler. The inexpensive official-MLB schedule gate now wakes heavy prediction work **10–39 minutes** before scheduled first pitch (formerly 16–31). The worker still independently validates pregame status, original timing (**8–30 minutes**), actual completion before first pitch, and create-exclusive immutable original records. A gate wakeup is NOT a valid prediction; extra early/late workers will safely skip rather than timestamp retroactively. Existing coverage and missing-original alert jobs remain enabled.

## 2. Empirical historical scoring-distribution research

`python -m cloud.v17_scoring_research` reads all **261 verified 2020–25 MLB postseason finals** and checks a simple previous-season-only mean total baseline under several Poisson/Gamma-Poisson negative-binomial dispersion assumptions. Dispersion alpha is chosen on **2021–22 only**; **2023–25** are reported separately. These retrospective scores **are not game-specific archived pregame estimates, nor pristine untouched evidence** because later seasons have already informed broader project work.

The [measured V17 result summary](V17_SCORING_RESULTS.md) includes 131 later-season finals; the JSON report `outputs/v17_research/distribution_study.json` contains the comparison of out-of-year log loss and under 3.5/4.5/5.5/6.5 Brier scores for every candidate. The historical work does **not automatically rewrite the live dispersion factors**, since aggregate total distributions cannot separately identify shared game-level versus team-level noise or validate matchup-specific coefficients.

## 3. Truly prospective report for every saved total-run line

`cloud.v17_prospective.score_originals` includes ONLY one timestamp-valid `original_pregame` record per game (or legacy missing-kind originals). It excludes revisions, early previews, invalid or absent full PMFs and games without official final scores. It publishes:

- Home-win Brier vs Elo **on the same cohort**;
- Total-run MAE, signed over-/underprediction bias, mean prediction and mean actual;
- Separate Under 3.5, 4.5, 5.5 and 6.5 Brier scores, predicted mean, actual empirical frequency and counts in probability calibration buckets;
- Forecast model versions represented. These mixed-version summaries are descriptive, not a true paired A/B trial.

If no eligible game has settled, the report shows **zero** and unavailable metrics; it does not invent a calibration rate. Fewer than 30 originals always carry an uncertainty warning.

## 4. Verified player information, not guesses

The official MLB live boxscore often publishes a nine-player batting order without hitter-handedness values. The pregame capture function now falls back to `gameData.players` in the **same official timestamped MLB response**, checking the player's identity. No retrospective player lookup, guessed hand or newly retrieved postgame data enters a frozen forecast. Full verified player game logs remain strictly earlier-date and require all nine IDs to match. Source uncertainty remains visible.

An explicit new model version records the changed data provenance: `17.0.0-audited-pregame-context`.

## 5. Bullpen/park/weather/lineup overlays: A/B instead of unsupported coefficients

Because these are experimental contextual rate changes, each eligible NEW game may receive an extra create-exclusive `without_experimental_context` shadow. It holds the historical scoring model, official player/starter information, postseason correction and simulation seed constant while neutralizing **the additional uncalibrated lineup, roster-bullpen, park and weather multipliers**. The original primary forecast is NOT altered. The comparison is scored on the same later genuinely completed games with winner Brier, total-run MAE and under-6.5 Brier.

Park and weather remain neutral in the normal hosted workflow unless independently enabled with supporting data. Roster bullpen workloads and sources should be used for diagnostics until retrospective and prospective validation supports additional coefficients. The shadow is skipped if insufficient pregame time remains and cannot delay or replace the genuine final original.

## 6. Portfolio, security and reproducibility

- Canonical GitHub repo: https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model.
- The new GitHub Pages URL was verified from the successful October 14 production deployment: https://andys3-design.github.io/MLB-Postseason-Forecast-Model/.
- New offline tests guard handedness provenance, timing, full PMF integrity, duplicate exclusion, same-cohort metrics and season separation.
- Existing historical research and model defaults are preserved for reproducibility. Deleting legacy scripts or imposing arbitrary pinned package versions without testing could disrupt the cloud worker and is not part of this release.
- The remaining priorities are more **genuinely prospective completed originals**, paired confidence intervals, evidence for any proposed distribution/park/weather/bullpen parameter change, and a reliable final-window capture rate under GitHub schedule delays.

## Reproduction

From the application folder:

```bash
python -m unittest cloud.test_v17_quality cloud.test_v17_scoring_research -q
python -m cloud.v17_scoring_research
python -m cloud.worker render
```

All modifications must pass project regression tests in GitHub Actions; do not backfill existing games with new 'pregame' predictions after first pitch. This is an evolving research system, not a validated claim of profitable or superior game predictions.
