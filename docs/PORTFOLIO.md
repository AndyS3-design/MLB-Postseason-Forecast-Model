# Portfolio and résumé guide

This project can demonstrate **Python, data engineering, applied machine learning, GitHub Actions, cloud deployment, auditability and reproducible research**. Describe only the parts actually built or verified, and update the wording as the independent performance evaluation develops.

## Concise project entry

**MLB Forecast Lab — Automated Baseball Prediction & Analytics Pipeline**

*Python · Pandas · NumPy · scikit-learn · GitHub Actions · GitHub Pages · MLB/Retrosheet data*

- Built and deployed a Python MLB forecasting pipeline that ingests historical baseball game logs and official game data, creates probabilistic score predictions, and publishes a mobile-friendly static dashboard.
- Implemented recency-weighted Poisson run modeling with support for **2016–2025** historical seasons and **12,000 simulated outcomes per cloud forecast**, alongside an Elo winner-probability baseline.
- Automated scheduled pregame runs, official prior-start pitcher backfills and postgame result settlement using GitHub Actions; recorded forecast creation timestamps and model/data coverage for traceability.
- Designed safeguards against look-ahead bias, preserved original pregame forecasts separately from explicitly labeled revisions, and added automated tests for cutoff rules, data identity and revision handling.

**Do not yet add** claims such as “80% win prediction accuracy,” “outperforms sportsbooks,” or “ten years increased accuracy by X%.” Those outcomes are not supported by independently verified prospective evidence.

## Good interview demonstration

1. Open the [dashboard](https://andys3-design.github.io/MLB-Postseason-Forecast-Model/) and show a stored prediction with its timestamp and expected runs.
2. Trace it backward from `site/data.json` to `cloud_records/predictions/` and `cloud/worker.py`.
3. Explain how the preflight gate, before-first-pitch cutoff and earlier-game filters reduce data leakage.
4. Show an original versus updated pregame record to explain reproducible provenance and change tracking.
5. Describe a time the pipeline produced missing-pitcher warnings and how verified boxscore backfill improved **data coverage**—not automatically predictive accuracy.
6. Show the GitHub Actions test/deploy jobs and discuss the limitation of best-effort schedules.
7. Explain the difference between a representative integer score and mean expected runs from a probability distribution.

## Engineering lessons to discuss

- **Data quality:** A model can identify a starting pitcher but still lack enough confirmed earlier starts for a reliable effect.
- **Time-aware ML:** A historical dataset can be accurate for later analysis but invalid as a pregame feature if it was not available at prediction time.
- **Cloud workflow reliability:** Two jobs editing the same branch can cause git push conflicts; serialize jobs and sync before writing.
- **Integrity and observability:** Timestamped predictions, logs, explicit missing-data warnings and benchmark metrics help prevent misleading performance claims.
- **Communication:** The UI distinguishes descriptive ratings, probabilistic run expectations and the unconditioned highest-probability exact score.

## Screenshot / portfolio checklist

Capture only after the relevant result is verified:

- [ ] Public website with one original forecast and visible pregame timestamp.
- [ ] GitHub Actions checks, model run and successful Pages deploy.
- [ ] Architecture diagram from [ARCHITECTURE.md](ARCHITECTURE.md).
- [ ] Original-versus-revised record comparison with clearly labeled timestamps.
- [ ] Data coverage audit showing actual historical years and starter counts.
- [ ] Prospective scorecard after enough new settled games, including Elo comparison and uncertainty.

## Future résumé improvement

Once meaningful out-of-sample results are available, add the **exact sample size**, evaluation period and comparative errors. Keep algorithm-development results separate from prospective holdouts; avoid turning retrospective optimization into a claim of independently tested accuracy.

**Framing for information-security-related roles:** Emphasize automated pipelines, provenance, change control, data-integrity checks, audit logs and reproducibility. Do not claim formal security certifications, penetration-testing functionality or guarantees that this forecasting project does not actually provide.

## V17 resume-ready additions (accurate as implemented)

- Expanded automated forecast-integrity testing with strict event cutoffs, deduplicated official schedule gates, same-request lineup-handedness provenance and additional independent model-ablation variants.
- Developed a prospective scoring pipeline that grades every original forecast's **complete run-total distribution** against 3.5, 4.5, 5.5 and 6.5-run thresholds and compares win Brier scores to an Elo baseline on matching games.
- Built a separate chronological 2020–2025 postseason total-score distribution study without claiming an aggregate benchmark validates full player-level matchup predictions.
- Added transparent run-bias and model-version monitoring on the live static dashboard, with no retrospective rewrites of immutable original picks.

For information-security job interviews, demonstrate input provenance, allowlisted identity matching, immutable evidence trails and fail-closed source behavior—not unsupported intrusion detection or gambling performance. Link actual passing GitHub Actions runs and the published `docs/RELIABILITY_AND_VALIDATION_V17.md` when available.
