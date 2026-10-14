# V18 forecast integrity fixes

New forecasts use model version `18.0.0-forecast-integrity`. Existing original, preliminary, revised and research records retain their recorded version and values. These corrections change future forecasts; they do not establish improved predictive accuracy without prospective evaluation.

## Scheduling and retries

The schedule gate queries the Eastern official game date and adjacent dates, then checks the actual timezone-aware first pitch. Previously, querying only the UTC date and tomorrow could miss a West Coast evening game after midnight UTC.

Pending authorized lineup refreshes, preliminary updates and revisions can wake the worker during their existing eligibility windows. A first attempt that finds incomplete lineups can therefore retry. Existing frozen outputs, expired windows, malformed requests and game identity mismatches remain ineligible. The worker performs its own final checks before writing any forecast.

## Current-season batting

The maintained asset builder restores complete team batting totals from cached official boxscores before constructing rolling team features. Retrosheet observations are preserved. Missing or malformed observations remain unavailable and are reported in coverage rather than silently appearing as measured zeros. Current-game and later-date results do not enter pregame features.

This restores the intended relationship between historical training features and current forecasts: rolling on-base percentage and isolated power can reflect observed current team batting instead of always becoming their league priors.

## Home regulation expectation

The regression target is observed regulation runs. Home totals already reflect games with an unplayed bottom ninth. Treating that prediction as a full-nine-inning intensity and skipping the ninth again systematically reduces home scoring twice.

The simulator converts the observed home regulation target into an appropriate latent inning intensity before applying the actual inning rules. It uses deterministic quadrature over the shared environment and starter-duration profile, with analytic negative-binomial team mixtures, then solves for the intensity. This is a numerical approximation; the method and latent intensity are recorded in each new simulation configuration. Away regulation expectations and the existing extra-inning policy retain their meanings. Final expected runs can still exceed regulation targets because tied games proceed to extras.

## Prospective uncertainty

The main accuracy summary accepts valid original pregame records only, preserves compatibility with correctly timestamped legacy originals, and excludes ambiguous duplicate game IDs. It requires 30 settled unique games across at least 10 dates before publishing a date-cluster bootstrap confidence interval or statistical-significance flag.

## Regression checks

From `MLB_Forecast_Lab_Cloud_Automation_COMPLETE`:

```bash
python -m unittest cloud.test_v18_scheduling cloud.test_v18_batting cloud.test_v18_simulation cloud.test_v18_accuracy -q
python -m unittest discover -s cloud -p 'test_*.py' -q
node cloud/test_v14_site.cjs
```

The V18 CI workflow runs the complete cloud test suite with the existing pinned Python 3.12 dependencies. The production workflow also includes the four V18 regression modules before it generates or publishes forecasts.
