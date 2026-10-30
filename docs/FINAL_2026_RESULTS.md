# 2026 season closeout — MLB Forecast Lab

**Status:** completed 2026 postseason case study. Finalized October 30, 2026. Research code and forecasts are retained, the GitHub Pages dashboard is a historical demonstration, and the three recurring forecasting/evaluation schedules are paused. GitHub Actions PR regression checks and manual dispatch remain available.

## Executive summary

This is an educational, fully automated Python baseball forecasting and evaluation system—not a validated betting strategy or a claim of 90% winner-prediction skill.

- Data from Retrosheet and official MLB schedules, game feeds and earlier-date baseball information.
- Recency-weighted Poisson run-rate modeling, Elo benchmark and approximately 12,000 simulated outcomes per cloud forecast.
- Predicted winner, expected runs, representative exact scores, and model-derived run-total Over/Under and same-simulation winner-plus-Over event probabilities.
- GitHub Actions preflight, independently guarded pre-first-pitch original capture, append-only final settlement, GitHub Pages deployment, CI, and immutable timestamp/first-commit provenance checks.
- Research V23–V35: prospective shadow comparisons, model ablations, immutable record / concurrency checks, exact paired McNemar test, independent full official game denominator, team identity and probability consistency audits.

### Primary verified outcome

The *independently reconciled prospective cohort* begins on October 14, 2026. The final read-only V35 official-cohort run ([GitHub Actions results](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/41058727480)) reported:

| Metric | Verified 2026 result |
|---|---:|
| Official completed games in the monitored cohort | 11 |
| Valid original pre-first-pitch predictions | 9 |
| Missing originals, retained in the denominator | 2 |
| Correct original winner selections | 5 |
| **Complete-cohort, end-to-end winner accuracy** | **5/11 = 45.45%** |
| Valid forecast capture rate | 9/11 = 81.82% |

**No whole-cohort Brier score is available:** missing forecasts cannot be assigned invented probabilities. Among the **nine identically matched games** only:

| Predictor | Winners correct | Winner accuracy | Brier score (lower better) |
|---|---:|---:|---:|
| Published original | 5/9 | 55.56% | 0.218730 |
| Fixed Elo baseline | 8/9 | 88.89% | **0.207307** |
| V23 preregistered 50/50 blend | 8/9 | 88.89% | 0.212643 |

The exact paired McNemar test between original and Elo reported two-sided **p = 0.25**: this is a very small prospective matched sample, and the apparent Elo advantage is *not* established as statistically reliable.

### Run totals and joint outcomes

The comparison is limited to the **nine matched, integrity-checked frozen predictions**. The baseline is **261 official postseason games from 2020–2025**, with 2026 excluded from selecting baseline parameters.

| Metric | Original model | Fixed older-season baseline |
|---|---:|---:|
| Over 4.5 correctness | 8/9 | 8/9 |
| Over 4.5 Brier | **0.102832** | 0.108689 |
| Over 5.5 correctness | 6/9 | 6/9 |
| Over 5.5 Brier | **0.215827** | 0.223690 |
| Total-runs MAE | 2.388 | **2.307** |

The genuine saved, **same-simulation** winner-plus-Over 4.5 event occurred in 4/9 games (Brier 0.221287); winner-plus-Over 5.5 occurred in 3/9 (Brier 0.215963). Joint event probabilities were **not** created by multiplying unrelated marginal probabilities. Elo did not generate matching run-total/joint-event probabilities.

### Historical replay — separate from prospective outcome

A retrospective complete 30-game 2026 playoff study (V22–V25) reported:

| Candidate | Correct winner selections | Brier |
|---|---:|---:|
| Original historical model | 19/30 = 63.33% | 0.242547 |
| Elo | 19/30 = 63.33% | **0.235920** |
| V23 fixed 50/50 ensemble | 19/30 = 63.33% | 0.239086 |
| V24 feature-ablation candidate | 17/30 = 56.67% | 0.244700 |

The retrospective V24 classifier was trained on 2023 regular-season games, selected only against 2024 regular-season results, and reported 2025–2026 outcomes separately. It did not generalize better than Elo. V25 showed the fixed V23 blend changed none of the original 30 winner picks. These **retrospective** results were previously exposed to project development; they cannot be called untouched out-of-sample or combined with the nine original forecasts as independent trials.

### The 90% aspiration

The target was **not achieved**. Six of the first 11 monitored games were missed or incorrectly predicted. Even the next 19 perfect picks would yield only 24/30 (80%). On the same unreset cohort the earliest mathematical possibility is 54/60 (90%), requiring **49 consecutive additional correct predictions** and no missing games; this is not an expected or guaranteed outcome. A numerical threshold would still not establish a betting edge or sustained superiority.

## Reproducibility and evidence

- [Official full-denominator scorecard implementation](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/v30_official_cohort.py)
- [Scorecard regression suite](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud/test_v30_official_cohort.py)
- [First-commit verification](V28_GITHUB_FIRST_COMMIT_PROVENANCE.md)
- [Frozen originals](../MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions/)
- [Immutable settlement and concurrency protocol](V27_SAFE_SETTLEMENT_PERSISTENCE.md), [V29 first-writer guard](V29_FIRST_WRITER_GUARD.md)
- [V23 prospective study protocol](V23_PREREGISTERED_ELO_SHADOW.md), [V24 ablation](V24_WINNER_ABLATION.md), [V25 retrospective replay](V25_FIXED_BLEND_REPLAY.md)
- [V35/PR #45](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/pull/45), [last independent official-cohort CI report](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/41058727480)

Historical original forecasts, official settlement metadata, run distributions and joint odds are *retained unchanged*. The final 2026 closeout updates documentation and cron configuration only; it does not refit model weights.

## GitHub Actions after season closeout

**Recurring tasks paused:** `mlb-cloud.yml` (frequent forecasting/maintenance), `mlb-final-forecast-guard.yml` (independent backup), and `mlb-v30-official-cohort-ci.yml` (daily retrospective scorecard). The separate ChatGPT daily improvement task is disabled.

**Preserved:** source-code push/PR safeguards, read-only research workflows, and explicit **Actions → workflow → Run workflow** manual dispatch. Before using this system in any new MLB season, revisit official API/data availability, train/validation windows, game time, prospective cohort definition and evaluation policy. Re-enable scheduled workflows by deliberate reviewed PR; they do **not** restart automatically.

## Project limitations

This is a portfolio demonstration of applied modeling, data integrity, reproducible evaluation, reliability engineering, CI/CD and honest uncertainty. GitHub cron delivery is best effort; a legitimate original prediction must exist before first pitch. There is no guarantee of future performance, exact-score accuracy or investment profitability. No claim of cybersecurity scanning, security certification or verified betting returns is made. Retrosheet data attribution and historical research files remain preserved.

**Status of this report:** historical snapshot, not an automatically updating leaderboard.
