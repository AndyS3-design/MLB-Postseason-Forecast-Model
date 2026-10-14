# MLB Forecast Lab — Current Model Card (V8)

This is the maintained card for the baseball-only cloud forecasting service. Earlier extension-model documentation is archived in [docs/legacy_model_card_precloud.md](docs/legacy_model_card_precloud.md).

## Intended use

Educational/research forecasting for MLB game outcomes and scoring distributions. **Not** a validated source of guaranteed results or financial decisions. No bookmaker odds or prediction-market prices feed the deployed model.

## Inputs and architecture

- Training: 2016–2025 Retrosheet regular-season logs using recency-weighted Poisson regression, with model selection using earlier validation years.
- Current matchup: official MLB schedule and game identities; completed earlier-date MLB games; official previous starter appearances; verified pregame lineups/roster snapshots when available.
- Simulation: 12,000 vectorized game samples per cloud forecast, producing winner probabilities, expected runs, total-run distribution and an illustrative exact score.
- Research overlays: 2024-selected optional starting-pitcher rate correction, a conservative postseason scoring prior, descriptive offense/defense/pitching ratings and bullpen-workload audit.
- Model cache: SHA-256 content-addressed historical fit; current team and pitching snapshots are rebuilt at forecast time.
- Saved records: first-pitch-locked original forecasts, separately timestamped and labeled revisions, later official final settlement.

## Current evidence

See the [measured V8 study](docs/V8_RESULTS.md) for complete game-by-game findings and file links. The 28-game 2026 playoff replay is **retrospective** and lacks independently archived pregame pitcher and lineup IDs. It cannot verify the accuracy of a fully enriched pregame production forecast.

## Leakage control

The estimator uses only results from dates **strictly before** the target game. Future/current game finals are evaluation labels only. Official pregame snapshots are rejected after the game starts. The original forecast is never overwritten by subsequent updates or revisions.

## Known limitations

- In the 2026 playoff retrospective, projected combined totals were high on average (8.27 predicted vs 7.04 actual).
- Brier score on the 28-game winner replay (0.24192) did not beat Elo (0.23854).
- More features do not necessarily outperform simpler regularized alternatives.
- Postseason and bullpen workload adjustments require more outside-sample validation; user-supplied annual postseason context is not independently calibrated for causal use.
- Predictions depend on official data quality, Github-runner availability and first-pitch timing.
- Retrosheet information was obtained free of charge from and is copyrighted by Retrosheet (https://www.retrosheet.org/).

See [architecture](docs/ARCHITECTURE.md), [data/methods](docs/MODEL_AND_DATA.md), [validation](docs/VALIDATION.md) and [operations](docs/OPERATIONS.md).
