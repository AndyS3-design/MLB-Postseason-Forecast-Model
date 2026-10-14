# Catch-up Maintenance Safeguard (V11)

**Problem:** GitHub Actions best-effort schedules may run late or be skipped. The five-minute pregame gate correctly skips expensive full-data refreshes when there is no nearby game, but skipping the scheduled daily maintenance job could leave yesterday's official final unsettled.

**Fix:** Each scheduled check reads `cloud_records/daily_maintenance.json`. If no completed official result import is recorded for the current **America/New_York calendar date**, the check runs a full refresh and publishes the results before resuming lightweight pregame checks. A short pregame job never updates the full-maintenance marker.

- Historical forecasts remain immutable; official finals are attached separately.
- The full refresh marker is written only when official final data import succeeds.
- Today’s game forecast is still intentionally targeted approximately 20 minutes before the scheduled first pitch. Maintenance is not an early preview.
- GitHub scheduled checks themselves remain best effort. This fix improves catch-up behavior but cannot force GitHub to start a job at exactly 7:40 PM Eastern.

**October 14, 2026:** Milwaukee at Los Angeles NLCS Game 3 is scheduled for 8 PM Eastern, so the target forecast time is approximately 7:40 PM Eastern. Before then, no original pregame forecast for that matchup is expected.

Run the cloud tests via `python -m unittest cloud.test_v11_daily cloud.test_cloud cloud.test_v7 -q`.

## Public dashboard: today's scheduled matchups

The browser now requests **today's official MLB schedule** and distinguishes a scheduled matchup from a **saved pregame forecast**. Until roughly 20 minutes before first pitch, it shows "forecast pending" rather than inventing a projected score. If GitHub runs late or the MLB schedule endpoint cannot be reached from the browser, the site explains the limitation. This feature does **not** download hidden game outcomes into the model or change saved predictions.
