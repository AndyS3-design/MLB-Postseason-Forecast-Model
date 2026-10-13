# Full 2025 retrospective validation run (performed while building this add-on)

**Source**: Bundled Retrosheet game logs + 2025 published postseason scores.
**Training**: 2023–2024 regular season. **Prediction evaluation**: 2025, 2,425 regular-season and 47 postseason games. No 2026 game results were available in this tool environment. Detailed 2026 pitching boxscores were **not** available locally; therefore the advanced 2025 model ran with basic historical features, not the richer pitching files on the user's PC.

This is a retrospective development evaluation, **not a pristine, previously untouched holdout**. No Kalshi prices are included.

| 2025 regular-season metric (lower is better except coverage) | Poisson | Existing NB | Wider NB | Constant NB |
| --- | ---: | ---: | ---: | ---: |
| Total-run CRPS | 2.6302 | 2.5436 | 2.5346 | 2.5454 |
| Exact-score log loss | 5.1963 | 4.8373 | 4.8184 | 4.8410 |
| Under-6.5 Brier | 0.2365 | 0.2218 | 0.2204 | 0.2236 |
| Nominal 80% total-run predictive interval coverage | 67.7% | 79.9% | 84.2% | 81.2% |

Elo winner Brier **0.24406**, advanced winner Brier **0.24412** (no clear advantage in these data). All score models' win marginals are aligned to Elo and are not independent winner forecasts.

For wider NB minus existing NB, paired game-date bootstrap 95% confidence interval for total-run CRPS was **[-0.0133, -0.0036]** in the 2025 regular-season retrospective analysis. This is a small improvement in that particular dataset, and the interval does not include modeling/selection uncertainty. Reusing this test set for further selection would inflate apparent certainty.

**DO NOT auto-promote a model.** The user's Windows PC has 2026 data and imported pitcher details: run the 2026 comparison locally using the included instructions, and reserve truly new future games for prospective validation.
