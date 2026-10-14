# V17 empirical study: postseason total-run tail shape

**Execution:** October 14, 2026, [V17 independent GitHub Actions run](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/38648190035), 99 passing tests. The complete historical experiment JSON and exact tested Python dependency versions are available as the `historical-run-distribution-v17` workflow artifact.

This uses **all 261 official 2020–2025 postseason game finals**. It deliberately tests only a *simple league-level previous-season mean* forecasting benchmark; it does not reconstruct 261 authentic archived game-specific pitcher/lineup predictions. No current-game outcome enters its earlier-year expected runs.

## Chronological setup

- Choose a Gamma/Poisson total-run overdispersion factor `alpha` using **2021–2022** games exclusively; 2020 supplies the preceding-year prior baseline.
- Examine 2023–2025 game finals separately (**131 games**). Those seasons are not fully untouched development holdouts, so results remain retrospective.
- Competing values: `alpha = 0, .05, .10, .15, .20, .30, .40`. Alpha zero is ordinary Poisson; in the benchmark negative-binomial family, total variance is `mean + alpha * mean^2`.
- Optimize early-year per-game total-run log loss, then disclose the same metric and Under 3.5–6.5 Brier scores on later years without changing the selection.

## Measured later-year scores (2023–2025, 131 games)

| Alpha | Total-run log loss (lower better) | Under 6.5 Brier (lower better) |
|---:|---:|---:|
| 0.00 (Poisson) | 2.875973 | 0.242908 |
| 0.05 | 2.771533 | 0.236604 |
| 0.10 | **2.746951** | 0.234494 |
| 0.15 | 2.751574 | **0.234284** |
| 0.20 (2021–22 selected) | 2.768941 | 0.235047 |
| 0.30 | 2.818427 | 0.237953 |
| 0.40 | 2.873409 | 0.240+ |

The early-year criterion selected **0.20**, but among later-year observations **0.10** had lower total-run log loss. The benchmark's postseason actual mean was **8.2061**, vs its forecast mean **8.2751**; average absolute total error was **3.20922** across all compared alpha settings, because adjusting dispersion does not change the expected total.

**Conclusion:** A simple Poisson baseline is too narrowly distributed for postseason totals in this archival exercise, but **one global selected dispersion factor is not clearly stable from period to period**. The production simulator has separate team/shared gamma shocks, inning rules, walkoffs, and extras; these aggregate score statistics alone cannot identify its individual team versus game components. Consequently, **no new production dispersion coefficient was set based on this experiment**. That is a positive integrity result, not an unfinished task.

## Next conclusive tests

Compare future actual, timestamped original predictions against equal-seed experimental dispersion variants on the **same unseen games**, measuring full-run PMF log score and Brier by run line. Report missing original forecast coverage, multiple-testing burden and paired uncertainty. Do not select the apparent winner on the same games used to claim validation.

Run `python -m cloud.v17_scoring_research` from the app folder to generate the detailed comparison and verify all 261 official final-score identities.
