# V21 experiment: can historical playoff rounds correct high projected run totals?

**Result: no defensible production adjustment yet.** This is a completed, reproducible negative research result, not a new version of the live prediction model.

**Run:** [GitHub Actions V21 research and test evidence](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/38683734935), 2026-10-15 UTC.

## Problem tested

The current V18 scoring engine/V20 presentation retrospective reconstruction of all **30 2026 postseason games through October 14** projected mean **8.0783** total runs, while the actual mean was **6.9667**. The model's per-game run-total MAE was **2.54284**. The largest overprediction was in the **16 Division Series games** (projected 8.0558, actual 6.1250).

Both Over 4.5 and Over 5.5 had been selected in all 30 model replays; the resulting hit rates were the same as blindly selecting Over every time. This is **not a demonstrated Kalshi trading advantage**.

## Before-2026 selection, historical chronological evaluation

Read exactly **261 verified MLB postseason final scores** from the existing 2020–2025 archival data, with independently recorded regular-season average scoring for each season. For each historical target season, construct a league-level runs forecast using **only completed previous postseason seasons** and that season's regular-season scoring baseline.

Explore weights `[0, 0.25, 0.5, 0.75, 1.0]` to blend an overall historical postseason-scoring ratio with a playoff-round-specific historical ratio. Select weight **0.25**, using MAE on **2021–2022 only**, before any later-year comparison.

| Period and metric | Previous-season global historical ratio | Selected 25% stage blend |
|---|---:|---:|
| 2021–2022: 77 game total-run MAE ↓ | 3.47968 | **3.47731** |
| 2023–2025: 131 game total-run MAE ↓ | 3.20445 | **3.17802** |

The gains of 0.0024 and 0.0264 runs/game are tiny relative to normal error. These are **league-level forecasts**, not historical V20 game-specific replays; the later years already informed the development of the project and are **not untouched data**.

The historical stage averages are inconsistent across years. For example, Division Series scoring in 2020 was high, while 2026's Division Series was unusually low. A deterministic correction that uses 2026's own unusually low results to reduce Division Series predictions would be **in-sample hindsight tuning**.

## Apply the previously selected historical blend to existing V20 2026 game-mean predictions

After fixing the weight at 0.25 from 2021–2022, download the exact immutable [30-game 2026 retrospective V20 scoring artifact](https://github.com/AndyS3-design/MLB-Postseason-Forecast-Model/actions/runs/38682612970) and multiply only each previously recorded expected total by the round adjustment estimated from 2020–2025. **Do not refit anything on the 2026 results.**

| Current V20 retrospective, through October 14 | No stage adjustment | Previously selected stage blend |
|---|---:|---:|
| Sample | 30 games | 30 games |
| Mean projected combined runs | 8.0783 | 8.0265 |
| Actual mean combined runs | 6.9667 | 6.9667 |
| Total-run MAE ↓ | **2.54284** | 2.56882 |
| Signed projected-minus-actual bias | +1.11168 | +1.05987 |
| Wild Card MAE ↓ (9 games) | **1.18253** | 1.20535 |
| Division Series MAE ↓ (16 games) | **3.19979** | 3.24635 |
| Championship Series MAE ↓ (5 games) | 2.88915 | **2.85498** |

The candidate marginally reduces overall signed bias, but makes overall MAE worse (+0.02598). Most importantly, the earlier-season Division Series ratio actually **raises** the 2026 Division Series projection from 8.0558 to 8.1175 runs, even though those games averaged only 6.125. That is the opposite of the needed correction.

**This is a mean-only sensitivity calculation, not 30 new full innings-level simulations.** It does not re-estimate model winner probability, the 4.5/5.5 Over probabilities, full PMFs or winner-plus-Over joint probabilities. Do not interpret its mean-only results as a strategy success rate or new model forecast.

## Decision and next evidence needed

**Keep the live model unchanged**: no retroactive editing of the frozen pregame original records, no altering the automatic V20 predictions or their probability distributions, no new postseason run correction coefficient. The selected stage-based adjustment is not a reliable enough improvement to ship.

The next properly testable change should address missing verified *game-specific* pregame data: starting pitchers, bullpen workload, confirmed lineups and season-specific team hitting features, rather than forcing all Division Series totals down just because 2026 games scored fewer runs. Independently preserve actual timestamped pregame inputs; skip unavailable inputs rather than inferring from postgame boxscores.

For new genuine future originals, compare the current model with counterfactual shadows on the **same games** and track mean-run signed bias, MAE, 4.5/5.5 Brier scores, winner Brier and combined-event probabilities. Avoid selecting the model on the same games used as the claim of accuracy. Prospective source timestamps and first-pitch cutoffs remain binding.

## Prospective scoring test added for Kalshi-style lines

The **underlying live model stays unchanged**. The existing immutable `cloud/v8_challengers.py` research-shadow pipeline now additionally saves `under_4_5_probability` and `under_5_5_probability` for **new shadow forecasts created before first pitch**, calculated only from each challenger's exact simulated final-run PMF. This permits same-game comparisons of the existing historical-playoff correction, no current-year adaptation, no-playoff-context, neutral experimental context and no extra starter correction.

Once official final scores arrive, the paired evaluator and **live dashboard's expandable alternative-model panel** report, **for each line separately**, the number of genuinely eligible matched pregame originals and challenger variants, plus both Under-line Brier scores. Missing saved PMFs or older shadows without those line fields count as **unavailable**, never zero-error wins. The original forecast is always saved first; no experimental values replace or rewrite a user's predicted winner or Over/Under probabilities.

This evaluates prospectively whether *removing* or altering context actually helps the real 4.5/5.5 markets before selecting any scoring-rate change. A high historical Over hit rate alone is inadequate, especially given 2026's retrospective construction and unverified past starters/lineups.

**Checks:** `python -m unittest cloud.test_v21_kalshi_shadow cloud.test_v8_challengers -v`. The research workflow and main forecast CI run these alongside their original cutoffs and score-simulation safeguards. GitHub notifications or the daily report may show `n=0` until enough truly timestamped matches settle.

## Reproduce the research (no unpinned dependencies)

From the application folder:

```bash
python3 -S -m unittest cloud.test_v21_stage_calibration -v
python3 -S -m cloud.v21_stage_calibration
# With the existing 30-game saved research results archive:
python3 -S -m cloud.v21_stage_calibration --v20-replay path/to/all_postseason_2026_v20_per_game.csv
```

The GitHub Actions workflow `.github/workflows/mlb-v21-stage-calibration-study.yml` downloads the exact source 2026 V20 artifact read-only **after** early-year model selection and uploads the full machine-readable V21 JSON. This module is research-only; it is not imported by or invoked from `cloud.worker` or `v4_workflow`.

**Caveat:** The users' 2026 postseason playoff scoring results are already known when this experiment is run. This retrospective comparison is diagnostic, not evidence of prospective trading profitability or future predictive advantage.
