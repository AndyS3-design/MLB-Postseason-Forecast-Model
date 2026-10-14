# V12 — Two-stage game-day forecasts

MLB Forecast Lab now produces **two independent pregame snapshots when the scheduling service starts the relevant jobs on time**. Neither one can be reconstructed or backdated once first pitch has passed.

## Forecast stages

| Stage | Earliest eligible time | Frozen JSON | Evaluation |
|---|---|---|---|
| **Preliminary** | From **10 AM Eastern on the game's official calendar date**; at least **45 minutes** before first pitch | `cloud_records/preliminary/{game_id}.json` | Paired research sample only |
| **Final pregame** | **8–30 minutes before first pitch**; default target around 20 minutes | `cloud_records/predictions/{game_id}.json` | **Primary original** in Brier, Elo, MAE and forecast-capture metrics |
| Requested one-time revision | Existing safeguarded revision window | `cloud_records/revisions/` | Clearly separate; not a second independent final |

The preliminary is marked explicitly **PRELIMINARY**, is always a genuine simulation using earlier-date history and a contemporaneous official pregame snapshot, and may have missing late pitcher or lineup information. The final is **newly generated** from newer verified pregame observations—not a copied preview or an overwritten prediction. If later information is identical, it is possible for preliminary and final probabilities to match.

Starting-pitcher historical backfill is performed before each stage runs, when possible, and uses games strictly from earlier dates. Each stage saves the real calculation-finish UTC timestamp, model version, selected score, full probabilities, expected runs, inputs' evidence/quality flags and training coverage. The preliminary has `forecast_kind: preliminary_pregame`, while the final has `forecast_kind: original_pregame`.

## How scheduling works

The lightweight GitHub Actions gate checks the official schedule every five minutes (GitHub timing is best effort). After 10 AM ET, if a game still lacks a preliminary and is more than 45 minutes from first pitch, a run is eligible. The earlier full daily maintenance workflow can prepare data but will not generate an early preview before 10 AM ET. The previously existing near-game gate separately attempts final predictions in its narrower window.

The preliminaries and finals are scheduled from **the same `master` workflow**, reusing its strict single-concurrency group. A later final can be saved even when an earlier preliminary already exists. Likewise, a final is still allowed when a preliminary was missed.

If an early game is already less than 45 minutes away when scheduling starts, **skip** its early preview rather than mislabeling a last-minute forecast as early. If GitHub misses the 8–30-minute final window, do not promote the preliminary to an original; show the preliminary and report a missing final for prospective capture accounting. Model calculations that finish after their respective cutoff are refused.

## How to read the dashboard

- On game day, the schedule distinguishes **preliminary available**, **final available**, and **both saved**.
- The matchup selector has a separate item for every frozen version.
- A final forecast shows its earlier preliminary score, total run expectation, win probability and original creation time when available.
- The **Accuracy & model health** section tracks matched, settled preliminary/final pairs, including paired win-probability Brier and total-run MAE. A missing final is never silently substituted by a preliminary.
- Only final originals are used in the primary prospective winner accuracy, calibration, Elo comparison, V9 capture rate and V8 shadow comparisons.
- Old original forecasts and explicit revisions are unchanged.

## How to verify

```bash
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
python cloud/preflight.py --help
python -m pip install -r requirements.txt
python -m unittest cloud.test_v12_two_stage cloud.test_v11_daily cloud.test_cloud cloud.test_revision cloud.test_v9_tracking cloud.test_v9_run_health -q
```

The GitHub CI job `V12 CI — Two-stage forecast safety` runs the expanded regression suite, checks that lightweight preflight runs before installing NumPy, and validates website JavaScript with Node.

**Accuracy limitation:** Having two forecasts does not prove that the final version is better. A fair claim requires sufficiently many newly completed games for which both original timestamps were genuinely before first pitch, paired errors on exactly the same games, a baseline, and appropriate statistical uncertainty.
