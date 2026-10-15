# V19 — Independent MLB final-forecast schedule backup and missed-original alert

## Why

On October 14, 2026 the Milwaukee–Los Angeles postseason game started without a saved final-window `original_pregame`. The existing main GitHub workflow could finish green because its preflight gate skipped model work and its health check was conditional on that gate. This is a scheduling/capture problem, not predictive accuracy. The separate early, model-version-corrected and lineup-confirmed provisional snapshots must remain unmodified and must NOT be relabeled as final.

## What is now installed

`.github/workflows/mlb-final-forecast-guard.yml` is a **separate** GitHub Actions workflow, scheduled at `2-59/5 * * * *` in addition to the original `*/5 * * * *` cloud workflow. Both are GitHub best-effort cron schedules: redundancy improves the chance of a pregame run, but does **not** create a guaranteed precise scheduler.

Every independent guard run checks **MLB's official current, previous and next Eastern game dates**, respecting the official `gamePk`, `gameType` and actual `detailedState`. It checks immutable originals in `cloud_records/predictions/<gamePk>.json` and refuses to consider a preview, a post-start creation, malformed JSON, or a wrong game identity a valid original.

- **Between 12 and 34 minutes before scheduled first pitch**: when the official game is still in a recognized pregame state and no original exists, the guard checks whether the normal main workflow is already running or queued. If not, it issues a native GitHub `workflow_dispatch` request for **the normal production worker**. The worker still independently enforces its original 8–30-minute creation window, status, real UTC timestamp and strict first-pitch cutoff. No research branch or made-up late prediction is substituted.
- **Less than 12 minutes before scheduled start**: when the original is still absent, the guard reports the game **at risk** in workflow output. It does not claim a successful forecast or silently shift the clock.
- **After official MLB status becomes In Progress, Final, Game Over or Completed Early**: if a valid original does not exist, the guard creates a **deduplicated GitHub issue** titled `[forecast-missed] MLB game <gamePk> began without a frozen final prediction`. There is no automatic retrospective backfill, and the error is durable even if the last normal green workflow was skipped.
- **Scheduled start passed but official status still Warmup or Pre-Game**: the guard does **not** declare the game started from the clock alone. The current normal original still cannot be backdated; a separate future late-pregame stage would require its own double official live-feed safeguards.
- **MLB schedule cannot be retrieved on all relevant days**: the independent guard fails explicitly; a source outage is not reported as no games.

Every guard run shows upcoming official scheduled games and the current UTC check time, so the next-game opportunity can be verified independently of the normal forecast dashboard. The monitoring start date is **October 14, 2026**, and the started-game alert lookback is limited to 18 hours.

## Security, notifications and limitations

The guard's token scopes are explicit: `contents:read`, `actions:write` (native workflow dispatch), `issues:write` (durable missed-game issue). It never writes a forecast. It only dispatches a normal master workflow and opens a repository issue. Issue notifications depend on the user's GitHub notification settings; a GitHub issue is **not** a guaranteed phone push notification. The workflow protects against duplicate dispatch while a recent main workflow is queued/running and against duplicate incident issues by exact title.

The guard is intentionally conservative. It does not silently switch to a third-party scheduler or use tokens not present in the repository. A true independent **external** clock would be needed for stronger timing guarantees if GitHub cron repeatedly starts late.

## Test and validation

```bash
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
python -S -m unittest cloud.test_v19_forecast_guard cloud.test_v18_scheduling cloud.test_v9_run_health -v
python -S -m cloud.v19_forecast_guard
```

The [V19 CI workflow](../.github/workflows/mlb-v19-guard-ci.yml) runs the tests and verifies upcoming/current games against actual MLB API data. This is not proof of any future game winner or total-run accuracy.

The next operational milestone is a **real, newly scheduled MLB game** whose V18+ final original is saved, verified on GitHub and published between 8 and 30 minutes before its scheduled first pitch. The backup guard will continue to report unmet conditions; it cannot manufacture that proof in advance.
