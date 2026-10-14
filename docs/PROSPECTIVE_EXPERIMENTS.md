# Prospective model comparison (V8)

This research capability compares alternative scoring assumptions on **new games only**. It was introduced after the October 2026 replay, to avoid reusing the same playoff results repeatedly as evidence of model improvement.

## Purpose

The V8 [playoff replay](V8_RESULTS.md) found overestimated postseason totals in a small historical sample. It did not establish that a new coefficient would improve accuracy. The correct next step is a **prospective comparison**: make competing predictions before the result exists, save them, then evaluate the same games on equivalent terms.

## What is frozen before first pitch

The maintained worker saves the original production prediction to:

`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions/<game_id>.json`

It may then generate independent research variants using the **same** cutoff-exclusive game history, official pregame snapshot and historical model assets. Research output is stored separately in:

`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/challengers/<game_id>.json`

That file records its own timestamp, model version, original-forecast timestamp, and independent probabilities. It cannot be created after the game starts, and its presence does not overwrite the original.

If research computation would run past first pitch, it is skipped. The main prediction remains preserved. Previously played games are **not** retroactively given pretend pregame shadow forecasts.

## Initial tested alternatives

| ID | What changes | What remains the same |
|---|---|---|
| `without_extra_starter_correction` | Disables **only** the optional additive pitcher correction calibrated to 0.25 | The learned run model still contains team/starter features; this is **not** a “no pitching” model |
| `without_postseason_context` | For playoff games only, suppresses the league-level run reduction applied in the main forecast | Same teams, starters, historical model, and verified pregame information |

Both use the existing game-simulation engine and 12,000 simulations each. The main published forecast is unaffected.

## How future results are evaluated

For each new settled game with a timely, valid original and a timely shadow record:

- Home-win Brier error, where **lower is better**.
- Absolute combined-runs error, where **lower is better**.
- Under-6.5 probability Brier error, where **lower is better**.
- Number of matched games evaluated.

Results are paired: the original and challenger are scored on **the same games**. Separate playoff and regular-season results must not be mixed into an apparent playoff sample. Report confidence intervals after sufficient games; a one-game difference does not demonstrate superiority.

### Rules for changing the main model

1. Declare which variant and metric are being tested *before* its results are known.
2. Save each forecast before first pitch with its model version and source coverage.
3. Compare equivalent games and report the sample size, missingness and uncertainty.
4. Require an independent chronological evaluation before approving a new production coefficient.
5. If a change is approved, save it under a new model version, and never revise the historical original records.

## Safety and known limitations

- GitHub scheduled jobs can be delayed and may miss the eligible game window.
- Pitcher coverage, official lineup availability and bullpen fatigue proxies can remain incomplete.
- The research variants are not a leaderboard or automatic winner selector.
- All validation is baseball-only; no sportsbook odds or market-price features are used.
- A prospective sample will take time to accumulate. The prior 28-game playoff replay is **retrospective** and does not count in these metrics.

See [operations](OPERATIONS.md), [model and data](MODEL_AND_DATA.md), and the [V8 measured evidence](V8_RESULTS.md).

## Operational capture denominator

From October 14, 2026 onward, the [V9 monitor](V9_PROSPECTIVE_MONITOR.md) independently reports which imported finished games did or did not have a valid original pregame forecast. This addresses **selection bias**: evaluating only games with predictions can hide games missed because of delayed GitHub runs. Capture rate is not forecast accuracy, but both should be disclosed when evaluating a deployed model.
