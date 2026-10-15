# V20: winner pick first, exact score conditional on winner — not a betting guarantee

## Why the October 14 dashboard was misleading

The user's October 14 Milwaukee Brewers–Los Angeles Dodgers screenshot highlighted Dodgers **3–2** as the unconditional highest-probability exact score (5.233% of 12,000 runs) while the *actual model favorite* was **Milwaukee Brewers at 53.775%** to win. The model's separate total-run forecast was **Over 5.5 at 64.758%**. Someone reading the large Dodgers-winning score as a Dodgers **winner pick** would misread the forecast.

All those statistics can simultaneously be true. The biggest probability assigned to a *single score* can belong to the team that is less likely to win after aggregating **all distinct scores**. Similarly, 7.47 expected total runs is a mean—not the exact total in the modal individual outcome, or a guarantee of Over 5.5.

### Corrected primary display for that same immutable pregame snapshot

- **WINNER PICK: Milwaukee Brewers, 53.8%** (from 1 − 0.46225 for home Dodgers).
- **Most likely exact score IF THE MODEL PICK WINS: Brewers 3–2 Dodgers**, with 4.225% probability across all simulated outcomes, approximately 7.86% **conditional on a Brewers win**.
- **Over 5.5 runs: 64.8%**, Under 5.5: 35.2%. These refer to all scorelines, not the subset in which Milwaukee wins.
- Secondary, explanatory section: **Unconditional most frequent exact score: Dodgers 3–2 Brewers, 5.233%**. It does *not* change the winner pick.

This is a presentation correction, **not a new or retroactively modified October 14 forecast**. The saved `projected_score`, `v6_display_score` and `modal_exact_scores` remain the actual unconditional mode. The older frozen versions (original preliminary, updated V13, official-lineup update) stay create-exclusive and immutable.

## New forecast data and historical fallback

The simulator now publishes **both distinct statistics**:
- `v6_display_score`: unconditioned exact mode over **all** final scores, unchanged.
- `favorite_aligned_score`: highest-probability exact score **among final outcomes where the team with the greater overall win probability wins**. Stores the home/away runs, probability among **all** simulations, probability **conditional on that favorite winning**, actual side and method. Uses the original 12,000 or other simulated draws; no extra model is fitted.

The worker saves `favorite_aligned_score` separately on any newly written original or preliminary forecast. No existing files are rewritten or reclassified for performance evaluation.

The dashboard reads the new explicit metadata whenever available. Earlier frozen records can be visualized from their saved **11 × 11 score-probability grid** only if the most frequent uncapped favorite-win score beats each ambiguous 10+ aggregated cell. If the historical grid is missing, malformed or contains a potentially larger 10+ aggregate, the dashboard states that an exact favorite-win score is unavailable rather than guessing. It never treats the top seven unconditional modes as a complete favorite-side ranking.

## Different probabilities, different uses

A displayed winner pick probability is based on the **sum of all outcomes that winner wins**. The winner-aligned score probability is a much smaller probability of **one exact outcome**. The over/under row is computed from the original complete *total run PMF*. A **joint Dodgers win + Over 5.5** or **Brewers win + Over 5.5** wager requires separately calculated *joint outcomes from the simulation*, and cannot be computed by simply multiplying two marginal percentages or by using the modal score as a total-over call. No bookmaker price, odds, or claim of profitability is implied.

## Checks

Run from the application folder:

```bash
python -m unittest cloud.test_v20_winner_score cloud.test_v13_score_presentation cloud.test_v14_totals -q
node cloud/test_v14_site.cjs
node cloud/test_v20_winner_site.cjs
```

The V20 workflow verifies the real frozen October 14 preview, winner-aligned and unconditional score modes, every saved half-run probability, unchanged archived bytes and fake/ambiguous data, plus normal two-stage and simulator safeguards.

Future empirical accuracy must continue to be graded with the **actual overall model win probability**, not whether a single exact-score winner matched the result. The changed visual ranking itself does **not** create new predictive skill or improve an over/under estimate.
