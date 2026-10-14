# GitHub cloud operations runbook

**Live site:** https://andys3-design.github.io/MLB-Postseason-Forecast-Model/

**Repository:** https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model

**Branch:** `master` · **Workflow:** `.github/workflows/mlb-cloud.yml`

## Hosting model

The project uses GitHub Actions for scheduled compute and GitHub Pages for the public static site. Your Windows PC does **not** need to stay on. GitHub schedules are best-effort: a late run can miss the eligible game window.

### Normal scheduled behavior

- `*/5 * * * *`: cheap schedule check every five minutes; heavy forecasting only if the check finds a game roughly 10–39 minutes before start; the separate worker still enforces an 8–30-minute completion window.
- `17 11 * * *`: daily maintenance at **11:17 UTC**, refreshing the historical/current baseball state and settling finished games.
- Worker acceptance for a *new original* forecast: generally **8–30 minutes before** the scheduled first pitch, with a valid pregame status.
- Manual workflow runs trigger full maintenance and deployment. **Manual runs do not automatically replace existing forecasts.**
- GitHub Pages is updated when the `deploy` job succeeds; the website URL remains the same.

There is no guaranteed exact 20-minute trigger; do not describe this as low-latency real-time infrastructure.

## Check a run from your phone

1. Open the repository's **Actions** tab.
2. Select **MLB Forecast Lab — game-time forecasts**.
3. Open the latest run and inspect jobs in this order: `check` → `forecasts` (when needed) → `deploy`.
4. If the check succeeds but the forecasts job is skipped, inspect whether a qualifying game was actually approaching; skipped heavy work is normal.
5. For a failure, open the red job and expand its failed step. Use the complete error message—not only “exit code 1.”
6. Inspect `MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/last_run.json` and the live site's last-update time to distinguish successful publication from a stale page.

## Local development on Windows

Use Python **3.12** to match GitHub Actions. From your repo root:

```powershell
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
py -m pip install -r requirements.txt
py -m unittest cloud.test_cloud cloud.test_v7 cloud.test_starter_backfill cloud.test_revision -q
py -m cloud.worker render
```

For a separate, controlled copy with Internet access and sufficient disk space, `py -m cloud.worker run` can refresh data and generate any *eligible* future predictions. It is not a command that can legitimately predict a completed game after first pitch.

To run the historical window comparison for research (may require time and memory):

```powershell
py -m cloud.compare_history
```

That comparison is retrospective, not a newly untouched holdout.

## Common failures and responses

| Symptom | Check | Safe response |
|---|---|---|
| Red X in `forecasts` | Expand the actual failed step logs | Correct the specific exception; don't repeatedly force a score to change |
| Git push rejected with `fetch first` | Competing commits or bot writes | Current workflow attempts pull/rebase and push; re-run after verifying no unresolved conflicts |
| `check` green but no `forecasts` job | Pregame window and schedule | This can be intentional. Validate official first-pitch time |
| Website unchanged after a successful run | New record count, `deploy` result, browser cache | A saved original will remain fixed; no eligible new game can mean no visible change |
| Missing starter history | `health.starter_backfill`, official game-log availability and prior start count | Keep data-quality warning if fewer than 3 verified starts |
| Original forecast doesn't update | `cloud_records/predictions/` exists | Working as designed; revisions are separate and only allowed before first pitch |
| Workflow queued or late | GitHub-hosted runner availability | Allow next check; skip late picks rather than fabricate a pregame timestamp |
| Model coverage smaller than expected | `health.run_model_training_years` | Verify Retrosheet archives under `data/` before claiming ten years |

## Responsible changes and rollback

1. Make changes in a Git branch when possible; read the diff and run the cloud tests before merging.
2. Never overwrite `cloud_records/predictions/<game_id>.json` to manufacture a better earlier prediction.
3. Keep changes to model weights distinct from presentation or documentation changes.
4. If a release breaks deployment, use GitHub's **Revert** action or a normal follow-up commit. Avoid force-pushing rewritten history.
5. Do not commit credentials, personal data or private API keys. The repository is **public**; `.gitignore` does not erase files already committed in Git history.

## Project maintenance checklist

- Confirm forecast and deployment workflows are enabled.
- Check recent prediction timestamps against actual scheduled start times.
- Review starter-history and lineup coverage.
- Track missing predictions and time-window failures.
- Review retrospective and prospective metrics separately.
- Attribute Retrosheet and record any changes in source behavior.

## V9 missed-prediction monitoring

A new independent `forecast_health` GitHub Actions job runs after an eligible main forecast job. It checks every game ID flagged by the preflight gate against an **original, valid timestamped forecast** saved in `cloud_records/predictions/`. If an expected game is missing, invalid or the worker reported `forecast_failed`, this health job **fails** and its GitHub Actions summary lists the game IDs. The separate website deployment job may still succeed with other valid predictions; the health signal must be reviewed independently.

The dashboard also displays a cumulative **pregame capture rate** starting October 14, 2026, computed only from official completed games already imported and dated before the current ET date. A blank or zero denominator is shown as **not measurable**. The machine-readable cumulative report is saved to `cloud_records/coverage_latest.json` and `site/data.json.prospective_capture`.

For failures, inspect `check` → `forecasts` → `forecast_health`, and `cloud_records/last_run.json`. GitHub schedules are best effort: do not backdate missed games. Also remember that an absent API final is **not** evidence that no prediction was captured; the monitor distinguishes these cases.

See [V9 monitoring definitions](V9_PROSPECTIVE_MONITOR.md).

## V17 source and schedule audit

The scheduler now opens its cheap wake window at 39 minutes and retains a recovery opportunity until 10 minutes before scheduled first pitch. The actual forecast is still rejected unless completed in the worker's original 8–30-minute window. GitHub scheduling is best effort; this improves opportunities, not guaranteed uptime. After a new pregame run, inspect the version, actual UTC completion timestamp and starters/lineups source coverage. Do not backdate a late missed final.

The renamed GitHub repository is https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model. Verified current GitHub Pages deployment URL: https://andys3-design.github.io/MLB-Postseason-Forecast-Model/ (from the October 14, 2026 successful deploy job).
