# V5 Totals-First Research Model Card

**Version:** V5 UI and multi-source research adapter layered on the existing V4 frozen research run model. This does NOT retrain, promise better predictive accuracy, or validate prices as profitable.

### Outputs
- Most plausible exact final score conditional on simulated most-likely winner: one score only.
- Winner and probability, expected home/away run totals, expected combined runs, total-run probability distribution, over/under/push for any line, 80% simulated interval, explicit sampling uncertainty.
- Market comparisons by bookmaker and **exact same line only**. No odds are invented. Reference bookmakers are not necessarily legally accessible in Florida. Benchmarks are **not** back-tested combinations of predictions.
- Optional manual Kalshi YES ask and fees; binary contract math assumes $1 payout for YES, excluding any unusual resolution terms.
- Optional manually logged bookmaker/exchange quote; append-only local JSONL includes event, line, direction, price, timestamp, model p and a hash, and is never treated as a real fill.

### Source data and validation
- Uses V4 core `v4_workflow.generate` and `v4_simulation.play_games` with captured actual start lineups (if official feed has announced them), prior pitcher and bullpen statistics, and optional scenario weather and home-park proxy.
- Uses `forecast_engine.fetch_schedule` for MLB schedule identity. `v4_sources.capture_official_pregame` prevents after-first-pitch snapshots from qualifying as pregame observations.
- Retrospective 2025 baseline tests exist for the V4 team-run model, but **V5 itself** is a UI/market presentation upgrade, not a new holdout-validated model.
- Per-market break-even odds and implied no-vig probabilities are arithmetic, NOT evidence of positive long-run EV. Event-specific liquidity, latency, fees and settlement rules matter.
- Older 2025/2026 development results have influenced design; prospective frozen records are required before using future accuracy as independent validation.

### Critical distinction
- Licensed Florida **sportsbook**: Hard Rock Bet.
- Out-of-state books: reference pricing only.
- Kalshi: exchange event-contract quote; do not assume representative sportsbook decimal odds are actual executable Kalshi YES asks.
- DFS player props (Underdog/PrizePicks): separate product type; price/multiplier and payout depend on selection/contest. PrizePicks team event contracts may sometimes match a market in principle, but must be matched by precise settlement language and own price data, not DFS player odds.
- Data vendor sample quotes might be absent, stale, indicative or behind a paid tier. A source name in the app does not mean a quote was retrieved or the account may transact there.

### Integration tests
`py -m unittest discover -q`; V5 tests cover PMF normalization, arbitrary fractional/integer lines and pushes, one consistent modal score, safe price math, provider names and event matching, stale pricing, separate DFS parsing, API key error redaction, deterministic official weather parsing, pregame-only timestamped quote logs. The historical project remains usable without V5.
