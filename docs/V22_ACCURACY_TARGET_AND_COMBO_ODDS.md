# V22 — Accurate winner-and-Over odds, auditable 90% target, and no hindsight fitting

## Goal vs what the postseason data can support

The requested goal is **at least 90% correct winners on all completed 2026 postseason games**. There were 30 completed games from September 29 through October 14, so this means **at least 27 correct winners**. The current V18 simulation engine / V20 winner-first interface retrospective replay obtained **19 of 30 (63.3%)**, requiring **8 more correct picks**.

A retrospective claim of 27/30 from a model optimized on these same 30 known outcomes is **not evidence of predictive accuracy**. Using future starting pitchers, game outcomes, revised records after first pitch or game selection after seeing results invalidates the test. This project must not repeatedly fit these games until the number looks good and present it as a betting edge.

The historical game-specific scoring test was honest but not sufficiently accurate for the requested objective:
- Winner picks **19/30**; Elo alone selected **19/30** on the same sample, and Elo winner Brier **0.235920** was lower (better) than the full model's **0.242547**.
- Over 4.5 selected on all games: **23/30**; Over 5.5 selected on all games: **19/30**. Both had the same hit count as the trivial always-Over baseline; this is not a sign that the model can separate individual high- and low-scoring matchups.
- Model favorite and Over 4.5 both hit **13/30**, and model favorite and Over 5.5 both hit **10/30**. These are actual combined events, not marginal win accuracy.
- The candidate historical playoff-round run-rate adjustment tested in V21 had **worse** 2026 retrospective run-total MAE (2.56882 vs 2.54284); it was rejected rather than hidden.

## Genuine improvement: joint probabilities measured from one simulation

V22 computes **actual winner + Over 4.5 / Over 5.5 joint event probabilities directly from the same individual final-score simulation draws**. New forecast records save `win_and_over_probabilities` with **home**, **away**, and **model-favorite** joint frequencies for each total line, plus the associated marginal Over. These are *not* products of independent win and total probabilities, which could be wrong because scoring and game outcomes interact.

The existing `home_win_probability`, `favorite_aligned_score`, unconditional modal exact score, run PMF, and all original model calculations remain unchanged. Prior frozen forecasts are never rewritten. If an older snapshot lacks verified joint probabilities, the dashboard says the combo estimate is unavailable rather than inventing one.

The live dashboard shows these separate joint chances only when computed from a recorded simulated game, and the prospective evaluation reports **n**, **Brier score**, **actual hit frequency**, and an explicit small-sample warning separately for both line combos. A combo event cannot be considered predictively accurate or profitable just because its expected runs or winning team looks favorable.

## Strict, reproducible 30-game acceptance gate

`cloud/v22_accuracy_gate.py` evaluates the saved V20 30-game research CSV. It requires **all 30 unique game IDs**, the original V18 model version, game identity, official pre-October-15 date cutoff, strictly earlier-date features and mathematically consistent joint probabilities. It reports:
- 27 of 30 winning games required for the numeric 90% threshold, versus the current 19 of 30.
- The number of additional correct picks needed.
- Wilson 95% confidence interval and Brier on the same games vs Elo.
- Over 4.5 / 5.5 and joint combination realized hits.
- Predeclared full-coverage and 55%, 57.5%, 60% selective confidence diagnostics for BOTH model and Elo. A selective subset can **never** be labeled 90% accuracy across all games.
- `can_claim_forward_accuracy_90pct=false` even if a retrospectively optimized model reaches 27/30: the sample is not prospective, and the code prevents this particular historical artifact from being advertised as live proof.

The corresponding CI workflow retrieves the **exact 30-game V20 artifact**, never fits or modifies its outputs, reruns these audits and uploads a machine-readable report.

## What would justify a real forecasting improvement?

1. Preserve the next **truly pre-first-pitch** original prediction and full joint score distribution; each missing cutoff must count as a capture failure, not be silently excluded.
2. Build only time-verifiable matchup predictors (starting pitcher and lineup confirmation, bullpen workload, projected park/weather conditions) with explicit missingness, never use postgame feeds as if they were pregame.
3. Select changes on older historical seasons and then test forward on an entirely new set of games. Require **matched calendar-time feature cutoffs** and compare probability calibration, total-run MAE, and joint probability Brier against the original **and** simple Elo/prior-total baselines.
4. For Kalshi decisions, separately account for actual contract prices, fees, liquidity and correctly computed joint probabilities. A high historical hit rate is not necessarily a positive expected-value position.

**Decision:** V22 improves scientifically auditable joint-event probabilities and the evaluation system. It **does not claim 90% winner accuracy** or secretly change the live model toward known 2026 outcomes. It's a step toward knowing whether future genuine improvements have arrived, rather than a claim that they have.
