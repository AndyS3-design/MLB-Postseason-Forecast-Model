# V28 research: first GitHub commit provenance (October 24, 2026)

The independent official full-cohort scorecard is still under development. This read-only V28 companion closes a different validation gap: **a JSON timestamp alone is not evidence of a genuine pregame forecast**.

For every saved original dated on/after the declared 2026-10-14 monitoring start, the audit reads the complete GitHub file-specific commit history, fetches the original JSON from its **first commit**, and requires:

1. A first-commit timestamp after the forecast's claimed creation and before its scheduled first pitch.
2. An original record that was not already settled when first committed.
3. Exact equality between first-commit and current original fields, including win probabilities, Elo, V23, run distributions, and same-simulation winner-plus-Over markets. Only later official_final/evaluation append is allowed.
4. A numeric official game ID matching the file name.

The audit **fails closed** for any invalid or unreadable tracked original. The CI job uploads a report as a run artifact; it never edits or rewrites production forecasts. It has no model coefficients and does not fit to 2026 outcomes.

**Limitations:** Git commit metadata can be manipulated and the scheduled start time in the forecast must be independently cross-checked against MLB. This audit is corroborating evidence, not cryptographic proof of pregame creation. The script covers *saved* records only. Games with missing predictions remain in the independent official full-cohort denominator and must be counted as misses. The unmerged V28 official-denominator scorecard is still needed for that full-cohort evaluation.

Run locally (with a read-only GitHub token):
```
python -m unittest MLB_Forecast_Lab_Cloud_Automation_COMPLETE.cloud.test_v28_first_commit_provenance -v
GITHUB_TOKEN=... python -m MLB_Forecast_Lab_Cloud_Automation_COMPLETE.cloud.v28_first_commit_provenance --repo AndyS3-design/MLB-Postseason-Forecast-Model
```

No 90% claim can follow from provenance checks or retrospective replay. At least 30 consecutive, predeclared, fully counted prospective postseason games and independent outcome validation are required.
