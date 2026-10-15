# V23 — Preregistered 50/50 model/Elo winner challenger

## Evidence and objective

Across 30 completed 2026 playoff games, the retrospective V18/V20 primary replay selected 19 winners (63.3%). Elo also selected 19 winners and had a slightly lower Brier (0.235920 vs 0.242547). Neither model has demonstrated 90% prospective accuracy.

## Fixed candidate, chosen before future games

    p_home_research = 0.50 * p_home_original + 0.50 * p_home_elo

The 50/50 weight is a fixed, transparent research hypothesis, **not** optimized on any 2026 postseason results. This is a winner-probability shadow, not a substitute for the simulation-based team-score forecast, total run PMF, or genuine V22 winner+Over joint odds.

Only NEW immutable official original pregame files carry the method, weights and research probability. Preview, revision and legacy files are not overwritten or retrospectively assigned candidate odds. All candidate inputs already exist in the exact same frozen pregame record.

## Evaluation

The V17 full-distribution score report adds winner_ensemble_shadow_v23: paired production, Elo and fixed-blend accuracy and Brier on exactly the same eligible finalized original snapshots. The grader rejects missing or forged blend values, different weights, changed formulas and after-first-pitch forecasts. Exclusions and distinct pregame dates are displayed. Fewer than 30 matched games are explicitly exploratory; 30 games alone still cannot prove a betting edge.

Run within MLB_Forecast_Lab_Cloud_Automation_COMPLETE:

    python -m unittest cloud.test_v23_elo_ensemble cloud.test_v17_quality cloud.test_v22_joint_markets -q

The V23 standalone CI workflow and main forecasting regressions enforce this frozen methodology. The published favorite and official primary probabilities do not change.

## Promotion rule

Do not replace the official forecast with the blend unless truly prospective, independent-date comparisons show improvement against BOTH the original and simple Elo in probabilistic scoring and calibration. Disallow cherry-picking games, after-outcome weight searches, or claims that a 27/30 retrospective fit proves future 90% accuracy. Preserve existing immutable records.
