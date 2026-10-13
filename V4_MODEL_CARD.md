# V4 Matchup Model Card (research prototype)

## Purpose

A date-safe MLB game forecast that explains variation between opponents by combining team offensive signals, historical starter performance, team bullpen use, manager hook tendencies, prior fielding-error history (coarse defense), optional confirmed batting order, optional individual reliever usage, and optional environment scenarios. It creates winner and exact-score predictions from the **same Monte Carlo game outcomes**.

## Inputs and data boundaries

- Training: 2023-2024 Retrosheet regular season and optional strictly-prior detailed pitcher data.
- Validation: 2024 run-score validation (tuning); 2025/2026 are retrospective development-holdouts, **not pristine**.
- Team offensive rolling runs, OBP, ISO and matchup-vs-starter-hand production are calculated strictly from completed games on **earlier dates**.
- Starter smoothed ERA, K/BB history, rest, and expected innings are calculated on earlier dates (8 starts maximum).
- Bullpen group features and prior manager tendencies from previously finished games are in the core scoring fit.
- Individual reliever fatigue from cached prior games; roster filtering only when pregame API provides bullpen IDs. It is a historical proxy, not authoritative medical availability.
- Official nine-hitter lineup capture and historical player batting lines strictly before the forecast date. If fewer than nine verified names, the lineup multiplier is neutral.
- Weather and park scenario adjustments are NOT validated by the historical scoring-fit regression and should be disabled for the most conservative comparison.
- Forecasts use the API game's official scheduled first pitch to block after-start pregame logs and lookahead lineup fetches.

## Model

`sklearn.StandardScaler` + `PoissonRegressor` for per-team regulation run expectation, trained in pooled team perspective. Single probability model is converted to inning rates by expected starter innings and bullpen performance, **normalized so SP/BP shaping does not double-count the run-model expectation**. Home runs 9th inning only if required. For ties after nine, simplistic extra-inning simulation; regular-season automatic runner influence approximated with elevated run rate (postseason excludes the automatic runner). Shared and team-specific gamma multipliers introduce extra scoring dispersion.

Data comes from MLB Stats API, Retrosheet, and user-recorded scenario options. The MLB API is not a guaranteed real-time source and fields may be missing.

## Observed core historical performance in this build

From 2,425 2025 regular-season games, all 2023–24 trained:

| Forecast | Regulation team-run MAE |
| --- | ---: |
| V4 team-run model | 2.4942 |
| Original backtested team-run model | 2.5146 |
| Constant 4.5 runs | 2.5515 |

Day-level paired bootstrap, baseline minus V4 team-run MAE: **0.0062 to 0.0354** (95% interval), but the historical period influenced model development. This confidence interval quantifies retrospective game-day sampling, NOT robustness to future distribution shift or real money ROI.

**Not evaluated** here: full-season player-level lineup overlays, pitcher pitch mix, availability by injury, causal park/weather effects, defense shifts, complete inning simulation calibration, actual Kalshi fills/fees. Do not claim V4 is more accurate for exact scores or superior to Elo for winners until separately tested.

## Avoid overstatement

1. A 100,000-game simulation does not make the inputs 100,000 times more accurate.
2. Monte Carlo confidence intervals are not model confidence intervals.
3. The most common exact score may have a probability near 3%; its displayed modal score is not a likely literal outcome.
4. Repeated tuning against 2025/2026 destroys pristine holdout independence. Prospective pregame records provide stronger future evidence.
5. A model can predict winners better but still produce negative expected return after Kalshi prices and fees. No exchange connection or trading recommendation is implied.
