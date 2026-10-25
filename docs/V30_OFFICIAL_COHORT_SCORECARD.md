# V30 read-only independent official postseason scorecard

**Research only; no changes to production probabilities, simulations, stored originals or model training.**

The predeclared monitored cohort starts **October 14, 2026**. V30 retrieves all official postseason Finals through the preceding Eastern date directly from MLB's schedule endpoint, recovering a scoreless Final only through that game's official live feed with strict game ID/date/team checks. Missing/invalid original predictions remain in the full denominator and count as incorrect; no probability is invented for missing games.

Every graded original is checked against the **first GitHub commit** by reusing V28 provenance verification. The original, simple Elo and the *already frozen* V23 50/50 blend are compared on exactly the same eligible games. The 2020–2025 official postseason CSV supplies a fixed historical constant baseline for Over 4.5/5.5 and total-runs MAE. The frozen same-simulation winner-plus-Over probabilities are scored only when internally consistent; **never** use the product of winner and Over marginals. Joint-event `events_occurred` is the number of actual combined events, whereas `correct` from `metrics` is binary classification accuracy at a 50% probability threshold; these are not interchangeable.

No fitting, feature selection, calibration or winner-weight tuning is performed on 2026 outcomes. V24/V25 retrospective experiments are not promoted. Run `python -m unittest cloud.test_v30_official_cohort -v` from the project directory. The PR CI independently runs the official cohort scorecard and uploads a read-only JSON artifact. The CI as-of date is fixed to **2026-10-25** to make the PR validation reproducible; future research runs should supply a new as-of date rather than rewrite historical reports.

**Interpretation:** full-cohort winner accuracy uses all eligible official finals; Brier and Over metrics use only matched valid frozen forecasts. A minimum 30-game genuinely prospective cohort with at least 27 correct winners is necessary for the stated numerical 90% milestone, but is not sufficient to prove sustained predictive superiority.
