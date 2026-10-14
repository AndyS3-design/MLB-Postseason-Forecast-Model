# V10 — Independent official MLB schedule audit

The V9 live forecast-capture rate uses imported official finals as its denominator. That is correct for measuring the performance of the service's stored data, but can be misleading if a data-import failure omits finished games entirely.

V10 adds a **separate, rolling seven-day, independent audit** against official MLB completed games (schedule endpoint, game IDs, game date, and official final score), and compares these with (a) the persisted result CSVs and (b) never-overwritten, timestamped original pregame forecasts.

## What is reported

- **Official completed games:** Recognized final games from the official MLB schedule with an MLB game ID and final scores.
- **Official capture rate:** Games from that complete official denominator with a valid original forecast from before the recorded first pitch.
- **Imported-results coverage:** The share of official completed games that appear in the local results files with matching date and score.
- **Missing original forecast**, **invalid/late original**, **missing imported result**, and **score/date mismatch** counts.
- **Audit status and window:** No false 100% success on off-days or before October 14, 2026; the audit explicitly states if missing, stale, unavailable, or incomplete.

Doubleheaders are separate game IDs. Postponed, canceled, suspended, live, and other non-final games are excluded; official finals without final scores appear in a separate integrity warning instead of being treated as complete.

## Automation, failure behavior and scope

The independent check runs only on the full cloud maintenance path (normally the **11:17 UTC** daily maintenance trigger or a manual run), *after* attempting the standard official result import. It does **not** slow the 8–30-minute pregame forecast window. Results are saved in `cloud_records/official_schedule_audit_latest.json` and published in `site/data.json.official_schedule_audit`. An outage or invalid API reply is explicitly marked **unavailable**. A date-old report is shown as **stale**, not silently treated as current.

The dashboard shows official coverage **separately** from V9's imported-final capture rate, with a warning if official finals are absent from the local CSVs. The check never creates or changes predictions, model coefficients, original pregame timestamps or settled outcomes.

The independent audit is deliberately limited to a seven-day rolling window (maximum 31 days if manually invoked in Python). It does not claim comprehensive historical schedule coverage, verify a true pitcher-announcement timestamp, or guarantee that GitHub's best-effort scheduled jobs always start on time. Today's games are never marked missed, and a postponed game's later rescheduling may change the date used in an official result. Investigate any identity conflicts before declaring a genuine missing forecast.

## Verification

From `MLB_Forecast_Lab_Cloud_Automation_COMPLETE`:

```bash
python -m unittest cloud.test_v10_schedule_audit cloud.test_v9_tracking cloud.test_v9_run_health -q
```

Run a manual API audit with a complete installed environment:

```bash
python -c "from datetime import date; from pathlib import Path; from cloud.v10_schedule_audit import reconcile; import json; print(json.dumps(reconcile(Path.cwd(), date.today()), indent=2))"
```

The independent CLI example **reads current official results but never changes saved predictions**. The full worker stores results and shows the dashboard panel automatically.

## How to judge accuracy

Coverage measures execution and data reliability, **not** correctness or betting returns. Continue using the original-only Brier, Elo, run-MAE, uncertainty, and prospective shadow-model comparisons. Do not retune a production formula on newly seen games and then advertise the same games as an independent prospective test.
