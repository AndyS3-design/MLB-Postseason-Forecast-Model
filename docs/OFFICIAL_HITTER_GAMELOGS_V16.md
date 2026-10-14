# V16: Complete, strictly earlier-date official MLB hitter game-log input

The Oct 14, 2026 confirmed-lineup preview was honest but neutral: a limited cache of 130 previously collected boxscores covered **368 Brewers** and **387 Dodgers** hitter plate appearances for the two nine-man orders. The prior `lineup_factor()` conservatively requires a minimum **400 lineup plate appearances**, so those previews did not change the 7.4695-run estimate.

A read-only check of the official MLB Stats API's `people/{player_id}/stats?stats=gameLog&group=hitting&season=2026&gameType=R,F,D,L,W` returned strictly prior-date player histories for the 18 exact confirmed batting-order IDs. Using the original model's same 60-game lookback, weighted batting events and 150-PA shrinkage prior, this produced:

| Game-day side | Verified previous-game lineup PAs | Original unchanged experimental lineup multiplier |
|---|---:|---:|
| Brewers | 2,118 | 1.02118 |
| Dodgers | 2,107 | 1.00859 |

These are *data sufficiency checks*, not evidence of prediction improvement. The multiplier formula (base wOBA + generic platoon proxy, clipped 0.88–1.12) was already in the model, but it is **experimental and not empirically calibrated on new unseen games**.

## Production use

- V16 makes up to 18 concurrent official hitter game-log API calls **only for pre-first-pitch scheduled games with a confirmed nine-player lineup**.
- Every event is filtered on exact MLB **game date strictly less than the target day**. This remains safe if the game-log endpoint is queried after earlier games or if 2026 moves on.
- Only supported completed game types R, F, D, L and W are accepted. Duplicate IDs with contradictory values, invalid game numbers, or malformed responses fail.
- If any required hitter source fails, the verified full-history adjustment is disabled and the old cached-boxscore/neutral path remains, rather than filling results with invented hits.
- The nine official batter IDs must be in the **same order** as the current MLB pregame snapshot. Otherwise verified history is rejected. Every saved forecast includes the precise original lineup order, audit status, plate-appearance totals, two lineup multipliers, and the source.
- Existing training features and the previously validated 2020–2026 postseason run correction remain the same. The research shadow forecasts reuse the very same saved official hitter-history inputs for fair comparisons, rather than silently using different inputs.
- Model version is advanced to `16.0.0-official-pregame-hitter-history` to identify the new source and distinguish it from V13 early forecasts.
- The actual original late pregame final is separately timestamped. Existing Oct 14 morning, corrected preliminary and lineup-confirmed snapshots are not modified or retroactively rescored.

The change is **not a promise that more hitter information improves accuracy**. The lineup-effect model is not an established profitable betting strategy, and small recent batter samples can be noisy. Future completed, genuinely timestamped predictions and a proper baseline comparison are required to validate the incremental overlay.

## Verification

```bash
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
python -m unittest cloud.test_v16_official_hitter_history cloud.test_v15_lineup_refresh cloud.test_v12_two_stage -q
```

The full V16 GitHub Actions suite also covers pregame cutoff, original immutability, historical data integrity and JavaScript runtime syntax. The earlier official 18-player audit is retained as a separate, read-only research workflow, not a modified historical forecast.
