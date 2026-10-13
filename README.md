# MLB Prediction Backtest — Expanded Research Kit

This contains a completed 2025 regular-season holdout and **47 actual 2025 postseason games**, plus importers for 2026 game logs, additional postseason seasons, historical sportsbook moneylines and executable Kalshi YES asks. The 2026 and odds holdouts are **not populated in this package**, because those data were not accessible in the environment that produced it. Nothing is fabricated.

## Run now (fully offline, included data)

```bash
python -m pip install -r requirements.txt
python run_all.py
```

Outputs are written in `outputs/`. See `MODEL_CARD.md` for the latest completed results and restrictions.

## Get 2026 data and historical playoffs automatically

On a computer with Internet access:

```bash
python ingest_mlb.py --as-of 2026-10-12
python run_all.py
```

The as-of date is **exclusive**; `2026-10-12` includes games through October 11 and excludes October 12, so even if you run it after today's first pitch, today's results cannot accidentally enter today's pregame predictions. For an updated future date, change the argument. The importer downloads an official schedule archive for each month and caches it under `data/mlb_api_json/`; to ingest previously saved schedules without network access, use `python ingest_mlb.py --offline`.

### What it adds

- **2026 regular-season holdout**: All finalized games before the chosen date, chronologically predicted with fixed parameters chosen before 2025. Writes `data/mlb_2026_regular.csv`.
- **2023–2026 postseason games**: Official postseason scoreboards, including completed 2026 games before the date. Writes `data/mlb_postseason_2023_2026.csv`. If an official API download is successful, it replaces the hand-transcribed 2025 scoreboard with source game IDs and known inning scores.
- **Postseason-specific evaluation**: Winner and under-6.5 Brier scores, accuracy, log loss, uncertainty intervals, and descriptive rest-days diagnostics. The 2025 test already ran; these additions will expand the sample when the official data arrive.
- **Sportsbook market baseline**: `market_baseline.py` scores historical timestamped sportsbook opening/closing moneylines (American format), removing market vigorish to compare forecast calibration. Requires `data/historical_sportsbook_odds.csv`.
- **Kalshi market ROI**: `market_backtest.py` matches pregame **executable** YES ask prices and fees to model probabilities, rejects lookahead/indicative quotes, and simulates a one-contract-per-game strategy with at least a five-percentage-point estimated edge. Requires `data/historical_kalshi_quotes.csv`. In the absence of that data, it reports **unavailable** rather than assumed profitability.

See CSV schemas under `examples/`. For accurate historical trading performance, the price record must be from *before first pitch* and represent an executable price; an external sportsbook line, the current displayed Kalshi portfolio value, or a market price observed after the event started is not a valid fill.

## Re-run individual analyses

```bash
python extended_eval.py
python playoff_diagnostics.py
python market_baseline.py
python market_backtest.py
python -m unittest discover -q
```

## Data and methodological caveats

- MLB's schedule API is a public web service, not guaranteed to provide complete historical executable odds. It returns final scores and inning-level run totals where available. Not every archived fixture has the same fields.
- Official postseason games are identified by game type `F/D/L/W`, which cover wild card, division, league and World Series. The API client requests all four. The hand-transcribed 2025 scoreboard has only final scores, not inning-by-inning scoring.
- Rest-day analysis describes associations and has no statistical power to establish a causal playoff-rest advantage. Individual bullpen usage requires separate pitch-by-pitch/box-score inputs; it's **not incorporated numerically**.
- The 2025 postseason sample includes only **47 games**. Its uncertainty is wide; do not use the point-estimate improvement as evidence of a profitable under strategy.
- Calibrated market-price profitability has **not been established**. The historical quote data needed for that test have not been supplied.

Retrosheet attribution: The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at www.retrosheet.org.
