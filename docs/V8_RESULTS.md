# V8 measured results — October 13, 2026

This page records **observed research results**, not future-accuracy guarantees. The maintained forecasting service is still **baseball-only**, without bookmaker or prediction-market inputs.

## 1. All completed 2026 postseason games (through October 12)

- **Sample:** 28 games (9 Wild Card, 16 Division Series, 3 Championship Series)
- **Historical fit:** 2016–2025 regular-season data; 12,000 simulations per game
- **Inputs:** game history strictly before the selected date, with no postgame-known starting pitchers or lineups
- **Observed:** 18 of 28 winners correct (**64.3%**)
- **Home-win Brier:** 0.24192 vs **0.23854 Elo** (lower is better)
- **Under-6.5 Brier:** 0.23189 vs **0.23181 prior 2025 playoff frequency** (essentially tied)
- **Combined-runs MAE:** 2.713 runs vs **2.545** using the prior 2025 playoff average
- **Mean predicted total:** 8.269; **mean actual:** 7.036
- **Experimental postseason context ablation:** context off MAE 3.002, context on MAE 2.713

**Interpretation:** The model's average run forecasts still overshot this small playoff sample. It did not consistently outperform baseball-only baselines, and the result does not measure the fully populated pregame starter/lineup system. The 2026 results had already influenced earlier development, so this is a retrospective replay—not an untouched test.

**Complete records:** [28-game audit](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_audit/POSTSEASON_2026_AUDIT.md) · [Per-game CSV](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_audit/postseason_2026_game_replays.csv) · [JSON metrics](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_audit/postseason_2026_audit.json)

## 2. Nested historical regular-season evaluation, 2022–2025

The study selected model settings on year **Y−1**, trained strictly on seasons before **Y**, and evaluated predictions for **Y**. The observed sample contains **19,404 team-game predictions** from four scored seasons.

| Model | Team-run MAE | Poisson scoring loss |
|---|---:|---:|
| Full scoring model | **2.44047** | −2.02171 |
| Without starting-pitcher features | 2.44322 | −2.01955 |
| Without bullpen features | 2.43950 | **−2.02185** |
| Without fielding features | 2.44004 | −2.02173 |
| Constant-runs baseline | 2.50079 | −1.99595 |

Lower is better. Starter features showed a modest benefit. The apparent gains from removing bullpen or fielding features were extremely small; they are insufficient to justify new production changes. Some years in this study previously influenced development, so do not describe it as pristine independent validation.

**Complete fold results:** [Chronological validation JSON](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_validation/walkforward_2022_2025.json).

## 3. Cached-model performance check

On a ten-season GitHub runner build:

| Metric | Before/rebuild | Repeat with cached fit |
|---|---:|---:|
| Full historical asset build | 8.234 s | 6.233 s |
| Frozen run-model fit/load | 1.949 s | 0.022 s |

Predictions matched exactly in that test. This is a **single controlled timing check**, not a guarantee of repeatable wall-clock improvements across all machines. The cache stores the trained historical model only; live team/pitcher features are rebuilt for new matchups.

**Performance evidence:** [Cache profile](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_validation/cache_profile.json).

## 4. Uncertainty and an independently retested pitcher coefficient

The 28-game playoff winner rate of **18/28 = 64.3%** has a **95% Wilson interval of approximately 45.8%–79.3%**. It is not a reliable claim of a future 64% winner rate. A date-clustered, paired 5,000-bootstrap resampling analysis estimates:

| Difference (MLB model minus comparator) | Observed | Approx. 95% interval |
|---|---:|---:|
| Winner Brier minus Elo Brier | +0.00338 | −0.00812 to +0.01528 |
| Total MAE minus prior 2025 playoff average MAE | +0.16825 | +0.08705 to +0.26581 |
| Total MAE with playoff context minus without | −0.28896 | −0.55244 to −0.00620 |
| Under-6.5 Brier minus prior playoff rate | +0.00007 | −0.01946 to +0.02095 |

Negative differences favor the MLB model. These intervals **do not eliminate retrospective model-development bias**. [Read the uncertainty JSON](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_audit/postseason_2026_uncertainty.json).

The optional additional **starting-pitcher correction weight** was retested across time-ordered 2022–2025 regular-season model fits. Selecting among 0, 0.25, 0.5, 0.75 and 1.0 on folds through 2024 again chose **0.25** (existing production setting). On the separate 2025 diagnostic, no additional correction had MAE **2.48879** / Poisson score **−2.04903**, while weight 0.25 had **2.48697** / **−2.05003**. The benefit is modest and does not establish postseason effectiveness. [Pitcher correction review JSON](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/outputs/v8_validation/pitcher_weight_review.json).

## 5. New prospective scoreboard and data-quality audit

The cloud dashboard now evaluates original time-stamped forecasts separately from any revised forecasts and displays available sample size, Brier scores, run errors, lineup/pitcher coverage and forecast lead time. Historical replays are **excluded** from those prospective statistics.

Bullpen workload diagnostics now disclose prior-three-day pitch counts and whether an official active roster was verified. They are **descriptive only** and not additional forecast multipliers.

## Limits and next required work

1. Accumulate many more **genuinely new** games with original pre-first-pitch predictions.
2. Evaluate probability calibration, pooled win Brier versus Elo, team-run/total-run errors, and uncertainty intervals.
3. Verify postseason-specific effects and bullpen workload on seasons or games not used to select their coefficients.
4. Track GitHub schedule delay, late/missed games and source freshness.
5. Do **not** fit a new “lower scoring playoff” coefficient to the same 28 games and advertise its in-sample improvement as independently tested.

**Retrosheet attribution:** The historical information used here was obtained free of charge from and is copyrighted by Retrosheet (https://www.retrosheet.org/).
