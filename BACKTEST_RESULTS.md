# MLB Historical Backtest: Observed Results

**Completed:** October 12, 2026  
**Data:** Retrosheet regular-season game logs, 2023–2025, supplied by the user.  
**Scope:** 7,280 usable games; 4,855 from 2023–24 and 2,425 from 2025.  
**Held-out test:** 2025, never used to tune the Elo parameters or fit run-model predictors.

## Summary

| Winner prediction | 2025 game count | Correct | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|---:|
| Elo team ratings (2024-tuned) | 2,425 | 1,337 | **55.13%** | **0.24406** | **0.68091** |
| Constant 2023–24 home-win rate | 2,425 | 1,317 | 54.31% | 0.24862 | 0.69038 |
| Poisson/negative-binomial run model, actual starting pitchers | 2,425 | 1,281 | 52.82% | 0.25078 | 0.69481 |
| Run model without starter history | 2,425 | 1,259 | 51.92% | 0.25090 | 0.69499 |

*Accuracy counts use a 50% home-win threshold. The constant baseline always forecasts a home win because its training home-win frequency exceeds 50%. The baseline's high accuracy is not evidence of good betting returns.*

| Under 6.5 runs prediction | 2025 accuracy | Brier | Log loss |
|---|---:|---:|---:|
| Constant 2023–24 under-6.5 rate | 66.93% | 0.22183 | **0.63580** |
| Run model with starter history | 66.89% | 0.22186 | 0.63661 |
| Run model without starter history | 66.93% | **0.22179** | 0.63688 |

*Under accuracy is misleading: because unders are comparatively infrequent, the models and the constant baseline generally predict 'not under.' The 2025 sample contained 802 unders (33.07%). Neither run model improved meaningfully over a baseline.*

### Uncertainty intervals

2025 calendar-date-cluster bootstrap (2,500 resamples); **positive numbers mean lower Brier loss (better)** versus the training-period constant baseline:

| Comparison | Brier improvement | Bootstrap 95% interval |
|---|---:|---:|
| Elo home-win vs constant home-win | **+0.004558** | **+0.001176 to +0.007930** |
| Run-model home-win with starter vs constant | -0.002161 | -0.005540 to +0.001459 |
| Run-model home-win without starter vs constant | -0.002284 | -0.006040 to +0.001400 |
| Run-model under 6.5 with starter vs constant | -0.000030 | -0.002297 to +0.002083 |
| Run-model under 6.5 without starter vs constant | +0.000037 | -0.002013 to +0.002153 |

These intervals describe uncertainty under a date-level resampling approximation; they do not account for all systematic differences between regular-season and postseason games.

## Exact modeling procedure

1. Read Retrosheet game logs and discard malformed/nonstandard observations; sort chronologically. Predict each date using only results from **earlier dates**. No same-day game can inform another prediction that date.
2. **Run model:** Poisson gradient boosting fitted to 2023–24 home/away regulation runs, with features for rolling offense, runs allowed, rest, current-season form, league runs, and a noisy starter-history proxy. The extra-inning total and winning chances are estimated empirically from 2023–24 extra-inning games. Overdispersion is estimated using 2024 validation residuals from a 2023-only preliminary model.
3. **No-starter ablation:** Repeat exactly without the actual-starter-related columns, because actual starters are recorded retrospectively and might not always have been known at the market entry time.
4. **Elo:** Maintain team ratings across years. Choose K-factor, home-field adjustment, and offseason regression by lowest Brier score in **2024 only**. Winning hyperparameters: **K=8, home-field adjustment=20 Elo points, offseason rating persistence=0.75**. Evaluate once on 2025.
5. **Scoring:** Accuracy, Brier score, log loss, calibration bins, and date-cluster bootstrap differences versus a constant historical-frequency baseline.

## Interpretation

- On the 2025 regular-season holdout, **Elo beat the constant home-win baseline in Brier score and accuracy**. This supports carrying forward a conservative team-strength baseline, but not automatically wagering on its predictions.
- **The run model did not beat the baseline for totals**, despite using recent scoring, starter history, and explicit empirical treatment of extra innings. Therefore there is no demonstrated under-6.5 forecasting edge from this approach.
- **This is not a backtest of Kalshi profitability:** historical tradable YES prices, bid–ask spreads, fees, and execution timestamps are absent.
- **This is not a playoff-specific validation:** yearly `glYYYY` files cover regular-season MLB, whereas postseason rotation usage, pitcher rest, bullpen deployment and lineup selection are meaningfully different.
- **It is not a current 2026 prediction model:** the attached data stop at September 2025, so it cannot accurately account for 2026 rosters, injuries, standings, and postseason performance without new data.

## Reproduce the results

Place `GL2023.TXT`, `GL2024.TXT` and `GL2025.TXT` into the kit's `data/` directory and run:

```bash
python -m pip install -r requirements.txt
python -m unittest -q
python backtest.py --offline --out-dir results_with_starter
python backtest.py --offline --no-starter --out-dir results_no_starter
python elo_benchmark.py
python evaluation.py
```

Relevant output files:
- `holdout_predictions_2025_ALL_MODELS.csv` — 2,425 actual outcomes and model probabilities, game by game.
- `results_comparison.json` — complete metric tables, bootstrap intervals, and calibration bins.
- `results_elo/metrics.json` — the tuned Elo parameters and holdout scores.
- `results_with_starter/metrics.json`, `results_no_starter/metrics.json` — run-model holdout metrics.

**Source attribution:** The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at www.retrosheet.org.
