# V14 — Most likely exact score vs expected runs; over/under 3.5–6.5

## Why a 7.47-run forecast can show an exact 3–2 result

The October 14, 2026 **Brewers @ Dodgers** updated preliminary `cloud_records/preliminary_revisions/849811_20261014T202744Z.json` contains **12,000 individually simulated final scores**. Across all games, it averages **7.4695 combined runs** (away 3.9619; home 3.5076), but a specific final score is an entirely different event. The simulation has a long right tail of higher totals, and a particular low score can be the most common single result without being likely in absolute terms.

The old V13 score display selected the highest-probability exact score **conditioned on the model's overall favorite winning**, producing Brewers 3–2 Dodgers (4.225%). This does **not** mean it is the most frequent exact score *among all outcomes*.

The archived score heatmap shows the actual unconditional exact score mode is **Brewers 2, Dodgers 3** (5.233%), followed by Brewers 3–Dodgers 2 (4.225%), Brewers 3–Dodgers 4 (4.125%) and Brewers 1–Dodgers 2 (3.817%). The Brewers remain the overall model winner at **53.775%** because that fraction sums *every* simulated Brewers win. An individual Dodgers-winning final can therefore be more frequent than any one Brewers-winning score even when total Brewers wins outnumber Dodgers wins.

V14 changes the default score display to the **unconditional modal exact final score** from the complete actual simulation. The most likely exact score is not a guaranteed prediction and normally represents less than 10% of all simulations. It does not need to be consistent with the winner-favorite label. Forecast winner probabilities and the full total-run distribution are unchanged by this purely presentational choice.

## Over/under totals from the full archived distribution

Each run total is an integer. For a half-run line L, `under(L) = sum(P(total < L))`, and `over(L) = sum(P(total > L))`. There is never a push on a half-run line. This is the model's own probability distribution, **not market odds** and without bookmaker margin.

For that archived 12,000-simulation October 14 preliminary:

| Total-run threshold | Under | Over |
|---|---:|---:|
| 3.5 | 14.375% | 85.625% |
| 4.5 | 20.700% | 79.300% |
| 5.5 | 35.242% | 64.758% |
| 6.5 | 43.600% | 56.400% |

As an example, the probability that total runs reach **6 or more** is **64.758%**, even though the unconditional most likely exact final has five runs. Over 5.5 aggregates dozens of distinct scores, while an exact score is only a single outcome.

## Historical records and data quality

Existing frozen V7/V13 previews, original finals and explicit revisions remain byte-for-byte unchanged. Old records generally contain the complete total-run probability distribution and an **11×11 capped score grid**. The dashboard reconstructs the unconditional mode for past records only if it can establish that no grouped **10-or-more-runs** grid cell could be the most frequent exact score. If this is ambiguous, it explicitly labels the old displayed score *archived illustrative*, rather than inventing an exact mode.

New records save the top uncapped simulated exact scores and the four over/under probabilities, so no reconstruction is needed for future games.

In all cases, the total-run probabilities are derived from the full archived total-runs PMF and validated to sum to 100%. A malformed or unavailable distribution results in **unavailable**, not fabricated probabilities.

## Verification and limitations

```bash
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
python -m unittest cloud.test_v13_score_presentation cloud.test_v14_totals -q
node cloud/test_v14_site.cjs
```

The Python and Node test suites cover the saved V13 preliminary, all four totals, distribution conservation, historical capped-grid safety, and a case where the exact-score mode disagrees with the aggregate model winner.

The 12,000 simulated trials have Monte Carlo noise and the baseball scoring model has much larger real-world uncertainty. These numbers are not demonstrated betting advantages. Preserve previously timestamped forecasts for truly prospective later-game calibration and MAE/Brier comparisons.
