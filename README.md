# MLB Forecast Lab
### Automated baseball forecasting, simulation and verifiable model evaluation

**Python · scikit-learn · Pandas · NumPy · MLB/Retrosheet data · GitHub Actions · GitHub Pages**

[**View the historical dashboard**](https://andys3-design.github.io/MLB-Postseason-Forecast-Model/) · [**Final 2026 results**](docs/FINAL_2026_RESULTS.md) · [**Architecture**](docs/ARCHITECTURE.md) · [**Résumé / portfolio guide**](docs/PORTFOLIO.md)

> **2026 postseason project complete — archived for portfolio demonstration (October 30, 2026).** Scheduled forecasting and daily research checks are **paused**, while manual GitHub Actions runs, CI checks, the public demonstration site and historical data remain available. This is educational research, not a validated betting strategy.

## What I built

MLB Forecast Lab is an automated, cloud-hosted baseball analytics project. It ingests historical baseball results and official MLB information, estimates scoring and winner probabilities, simulates possible final scores and publishes a mobile-friendly dashboard.

- **Baseball modeling:** Supports 2016–2025 historical regular-season training using recency-weighted Poisson regression, a fixed Elo benchmark and approximately **12,000 score simulations** per cloud prediction.
- **Probabilistic output:** Estimated home/away win chances, expected runs, an illustrative exact-score outcome, game-total distributions and Over/Under probabilities (including 4.5 and 5.5 runs).
- **Genuine joint forecasts:** Saves winner-plus-Over event probabilities from the **same simulations**, rather than multiplying independently estimated event probabilities.
- **Data engineering and CI/CD:** GitHub Actions preflight checks, data-quality flags, automated tests, original pre-first-pitch capture, postgame official settlement and GitHub Pages deployment.
- **Integrity and scientific method:** Immutable pregame predictions, first-commit provenance audits, GitHub SHA-guarded settlement updates, first-writer-wins concurrency protection, independent official complete-cohort scoring and statistically careful benchmark comparisons.

## Final performance: transparent results

The project's real monitored postseason cohort began on **October 14, 2026**, with the following outcome after the completed 2026 postseason:

| Outcome | Final figure |
|---|---:|
| Official games included | 11 |
| Valid frozen pre-first-pitch originals | 9/11 (81.8% capture) |
| Correct winner selections, **including missing originals as misses** | **5/11 (45.5%)** |
| Correct winners on the nine matched original forecasts | 5/9 (55.6%) |
| Elo winners on those exact same nine games | 8/9 (88.9%) |
| V23 fixed 50/50 blend on those same nine games | 8/9 (88.9%) |

Winner **Brier score (lower is better)** for the matched nine: original **0.218730**, Elo **0.207307**, V23 **0.212643**. On those nine original forecasts, the model called Over 4.5 correctly in **8/9** and Over 5.5 in **6/9**; total-runs MAE was **2.388**. A 2020–2025 postseason constant-runs baseline had total MAE **2.307**.

**A 90% win-pick target was explored but not reached.** The 2026 complete-cohort outcome is **45.5%**, not 90%. The older 30-game **retrospective** replay was **19/30 (63.3%)** for both original and Elo, and must never be confused with the live pregame cohort.

The matched Elo advantage is based on only nine games; an exact paired test returned **p = 0.25** and does not prove reliable future superiority. Missing original forecasts have no valid Brier probability and are *not* imputed.

[**Read the full results and methods, including Over and joint probabilities**](docs/FINAL_2026_RESULTS.md). The [final independent official-cohort workflow](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/41058727480) verified the counts.

## Repository guide

| Location | Purpose |
|---|---|
| [`MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/) | Maintained forecasting and scorecard code |
| [`v4_matchup_core.py`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/v4_matchup_core.py) | Frozen scoring-model training / feature construction |
| [`v4_simulation.py`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/v4_simulation.py) | Score simulations and probability distribution |
| [`cloud_records/predictions/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions/) | Immutable pregame originals and appended official finals |
| [`cloud/v30_official_cohort.py`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/v30_official_cohort.py) | Independent full-denominator postseason evaluation |
| [`site/`](MLB_Forecast_Lab_Cloud_Automation_COMPLETE/site/) | Static GitHub Pages dashboard |
| [`.github/workflows/`](.github/workflows/) | CI, research, manual deploy and archived schedule definitions |
| [`docs/`](docs/README.md) | Technical documentation and historic research |
| Older root-level V1–V7 scripts and guides | Legacy material retained for provenance; **not** the maintained entrypoint |

## Run the tests

Use Python 3.12. The maintained project lives in the subdirectory below (not the legacy root-level scripts).

```bash
cd MLB_Forecast_Lab_Cloud_Automation_COMPLETE
python -m pip install -r requirements-ci-py312.txt
python -m unittest cloud.test_v30_official_cohort cloud.test_v27_original_persistence cloud.test_v23_elo_ensemble -q
```

To render the already recorded dashboard locally without forecasting a future game:

```bash
python -m cloud.worker render
```

**GitHub Actions:** open [the Actions tab](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions) and manually dispatch the relevant workflow when appropriate. GitHub recurring forecast/backup/daily research schedules were intentionally **paused after the 2026 postseason**; see [season closeout and restart instructions](docs/FINAL_2026_RESULTS.md). Running a worker after a game begins must never be treated as a pregame forecast.

## What this project demonstrates

I built a working end-to-end system and learned to distinguish successful software deployment from actual predictive performance. The strongest engineering outcomes are **reproducible analysis, time-safe data pipelines, CI/CD, event provenance, immutable evidence, concurrency safety and frank reporting of model limitations**.

Historical source attribution: baseball data supplied by **[Retrosheet](https://www.retrosheet.org/)** and official MLB data endpoints. Independent educational project, not affiliated with or endorsed by MLB or Retrosheet. Results do not establish investment profitability or guaranteed future accuracy. No open-source license is granted by this repository; contact the owner for reuse permissions.
