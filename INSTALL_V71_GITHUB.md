# MLB Forecast Lab V7.1 — Verified Starter History Backfill

## The cause of the warning

The previous cloud worker downloaded only a small batch of recent MLB game
boxscores on each scheduled run. Even an established pitcher could have
fewer than three prior starts locally, so the model honestly reported
missing starting-pitcher history.

V7.1 searches official MLB pitcher game logs and imports prior **completed**
boxscores *for the named starters* immediately before constructing the model's
feature table. It verifies their MLB person IDs against the starters recorded
in the boxscore. If a pitcher truly has fewer than three MLB starts, his ID is
not announced, or the official API is unavailable, the model keeps the warning.

No final result from the forecast game's calendar date (or a later date) is
allowed into this calculation.

## Install on your existing GitHub `master` branch

1. In **GitHub Desktop**, open your repository
   `MLB_Backtest_Expanded_2026_Postseason_Markets` and verify the selected
   branch is `master`.
2. Choose **Repository > Show in Explorer** to open the *local repository root*.
3. Back up your project folder. Unzip `MLB_Forecast_Lab_V71_COMPLETE_GITHUB_FIX.zip`.
4. Copy **both** items at the root of the unzipped folder into your repository
   root, **merging** directories when Windows asks:
   - `.github` (this contains `.github/workflows/mlb-cloud.yml`)
   - `MLB_Forecast_Lab_Cloud_Automation_COMPLETE`
5. If Windows asks to replace matching files, accept. Do **not** delete any
   existing `data`, `outputs`, or `cloud_records/predictions` files.
6. In GitHub Desktop, review changed files; **Commit to master**, then **Push origin**.
7. On GitHub open **Actions > MLB Forecast Lab — game-time forecasts > Run workflow**.
   Use `master`. The first manual run may take a few minutes while official
   game logs and historical data are loaded.
8. Expand **forecasts** in Actions and verify that the tests, refresh, and
   Pages upload succeed. The **deploy** job must also pass before the website
   is considered live.

The workflow checks the official schedule every five minutes; it targets
forecasts 8–30 minutes before scheduled first pitch, centered around 20
minutes. GitHub can delay a scheduled job. The model will not publish a
backdated prediction if it ran too late.

## Test locally (from inside `MLB_Forecast_Lab_Cloud_Automation_COMPLETE`)

    py -m unittest cloud.test_cloud cloud.test_v7 cloud.test_starter_backfill -q

Expected result in the prepared release: **28 tests passed**.

## Where to inspect imported starter coverage

- In **Actions > (successful run) > forecasts** inspect the step that refreshes
  official data. Its `cloud_records/last_run.json` includes
  `starter_history_backfill` by game ID when a forecast was attempted.
- The hosted site's **Model audit > Show pitcher adjustments, data quality and
  limitations** now lists how many verified previous starts were found.
- New forecasts include `health.starter_backfill`, with before/after counts.

## Important limitations

- **An already-saved forecast is immutable.** Adding the missing data now
  improves *future* forecasts; it does not silently rewrite previous picks,
  past warning messages, or outcome evaluations.
- The individual starter adjustment also depends on
  `outputs/v62_pitcher_calibration.json`. If its validated weight is zero,
  the extra correction remains off even if all starts are present; the
  underlying fitted model may still use starter features.
- In this environment, tests use mocked official JSON responses; the live MLB
  Stats API download must run in your GitHub workflow. Verify the actual
  counts from that run. A green Actions commit alone does not prove that
  official pitching data were downloaded or that the site deployed.
- `2016–2025` history is included via V7's archive importer, but it does not
  guarantee historical starter detail for every season or pitcher.
- Baseball data only; no sportsbook or betting market inputs.
