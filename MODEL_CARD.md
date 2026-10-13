# MLB Backtest Extension — Model Card

Run date: **October 12, 2026**. Historical datasets included: 2023–2025 Retrosheet regular-season game logs supplied by the user; 2025 postseason scores manually transcribed from the MLB.com 2025 postseason schedule. 2026 API records and historical tradable Kalshi prices **not available in the execution environment** as of this run.

## What has actually run

| Holdout | Games | Model | Accuracy | Brier score | Comparison |
|---|---:|---|---:|---:|---|
| 2025 regular season | 2,425 | Elo home-team win | 55.13% | 0.24406 | Constant home-win: 54.31%, Brier 0.24862 |
| 2025 postseason | 47 | Elo home-team win | 48.94% | 0.24805 | Constant home-win: 55.32%, Brier 0.24819 |
| 2025 regular season | 2,425 | Run model under 6.5 | 66.93% | 0.22179 | Constant under-frequency: Brier 0.22183 |
| 2025 postseason | 47 | Run model under 6.5 | 59.57% | 0.24205 | Constant under-frequency: Brier 0.24995 |
| September 2025 regular season | 374 | Run model under 6.5 | 67.11% | 0.21508 | Constant under-frequency: Brier 0.22112 |

**Interpretation:** The apparent postseason under-6.5 improvement is too uncertain to claim an edge. Calendar-date bootstrap 95% interval for postseason Brier improvement: **-0.00755 to +0.02175**. Postseason Elo Brier improvement versus constant home-rate: **+0.00013**, 95% interval **-0.01166 to +0.01256**. Winner accuracy confidence interval (Wilson): **35.3% to 62.8%**. A single 2025 postseason is not an independent set of 47 identically distributed games.

## Model design and leakage protection

- Elo: K=8, home advantage +20 Elo points, offseason persistence 0.75. These values were chosen on 2024 **regular-season** results, not on the 2025 holdouts. Elo updates after all games on the date have been predicted.
- Run forecast: Gradient boosting Poisson separate home/away runs, trained on 2023–2024 regular season; scoring dispersion determined from 2024 validation. Final-score under outcomes include extra innings. Starter identity is excluded from these extended runs because historical actual starters are not guaranteed to have been known at contract purchase time.
- 2025 postseason scores were manually transcribed from the MLB.com calendar and have **no nine-inning breakdown**, so in the rolling **prior-game feature updates only**, final runs substitute for missing regulation runs. That affects playoff projections after earlier playoff games, especially games that went into extra innings. It is a simplifying approximation, not a formally validated postseason model. Targets always use accurate **final runs**.
- Neither market prices nor outcomes from games on the same date can enter that date's forecast. Market backtest refuses post-start, stale, non-executable, or invalid quote records. It reports nothing about profitability in the absence of timestamped quotes and fee information.

## Important gaps

1. **2026 regular-season data:** MLB's Stats API provides completed game records, but this runtime has no outbound download permission to obtain the 2026 season. `ingest_mlb.py` will download it when run in a networked environment, excluding games occurring on or after the configured as-of date.
2. **Historical postseason validation beyond 2025:** `ingest_mlb.py` fetches 2023–2025 MLB playoff schedules as soon as network access is available. They can be added for larger multi-year stress tests. Fixed model settings must not be tuned to the same season later used for a reported holdout.
3. **Historical moneyline odds:** `market_baseline.py` accepts actual timestamped historical sportsbook moneylines and scores no-vig implied probabilities versus Elo predictions. Historical sportsbook odds cannot establish Kalshi returns.
4. **Historical Kalshi tradable contracts:** `market_backtest.py` requires a strict game ID, pre-first-pitch executable YES ask, source, fees, and market outcome. Without such data, it deliberately produces `unavailable`. Screenshots of an indicative position value are not executable quotes.
5. **Unmodeled playoff context:** Individual reliever availability, bullpen usage by manager, starting lineups, ballpark weather and injuries require additional game-level snapshots and must be trained and backtested before assigning them numeric probability adjustments.

## Files

`outputs/extended_predictions.csv`: predictions for 2025 holdout + any imported 2026 games; `outputs/extended_metrics.json`: metrics; `outputs/postseason_2025_predictions_with_rest.csv`: historical playoff rest and forecasts; `outputs/postseason_diagnostics.json`: uncertainty and rest groups; `outputs/market_backtest.json`: Kalshi price-data status or evaluation; `outputs/sportsbook_comparison.json`: bookmaker-data status or model-vs-market metrics.

**Attribution:** The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at www.retrosheet.org.

Official sources: [MLB.com 2025 postseason schedule](https://www.mlb.com/postseason/history/2025), [MLB Stats API schedule specification](https://github.com/pseudo-r/Public-MLB-API/blob/main/docs/schedule.md), [Retrosheet game logs](https://www.retrosheet.org/gamelogs/).
