# Model design and data provenance

## Sources

| Data | Primary source | Use and qualification |
|---|---|---|
| 2016–2025 regular-season game history | Retrosheet game logs | Historical run-model training and rolling team features. Actual loaded years are reported per prediction. |
| 2026 completed games and current MLB schedule | Official MLB data endpoints | Team form, prior results, matchup identity and scheduled first pitch; game-day/future scores excluded from pregame features. |
| Starting-pitcher game history | Retrosheet detailed records and MLB official prior-game boxscores | Historical starter outings, innings/outs, earned runs and available strikeout/walk information. |
| Pregame starters and batting orders | MLB schedule and pregame snapshots where provided | Inputs are used only when available before the forecast time. Unconfirmed information remains a limitation. |
| Postseason scoring context | Included `data/postseason_context_2022_2026.csv` | A shrinkage-based research adjustment. Same-season snapshots must be available before the forecast date; not a proven causal factor. |

**Retrosheet notice:** The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact Retrosheet at https://www.retrosheet.org/.

## Forecasting sequence

1. Exclude games occurring on or after the target game's calendar date from feature history.
2. Compute historical team/league features and fit a **Poisson regression** for run expectations (`v4_matchup_core.py`).
3. Where data support it, apply separately documented pitcher and postseason research adjustments (`v4_workflow.py`).
4. Use the game's baseball inputs to simulate **12,000** possible outcomes (`cloud/worker.py`).
5. Save winner probability, mean team and combined runs, total-run probabilities, an illustrative score, the snapshot time, model version and coverage metadata.

The simulated **mean run total** may be fractional and need not equal the integer sum of the **illustrative score**. The score is one possible outcome, not the expected value rounded team-by-team or the exact-score mode in all cases.

## Historical training policy

- Eligible run-model fitting data: **2016–2025 regular season**, when all source files are available.
- Historical observation weights decay by a **three-year half-life**; this prevents older scoring environments from receiving equal influence to recent seasons.
- Candidate feature subsets and Poisson regularization settings are selected using **2024** validation data.
- The deployed 2026 run model is then trained through **2025**; 2026 results are not its training labels.
- The available-year list, coverage note and model commit are recorded in new pregame artifacts.
- The cloud model retains Elo as a comparison baseline, not an external bookmaker input.

**Crucial:** Ten years of input coverage is not evidence of better accuracy. The 2025 comparison is retrospective because 2025 data influenced earlier development. Only genuinely later, untouched predictions can test generalization.

## Starter and bullpen context

The `cloud/starter_backfill.py` stage looks up official earlier games for each identified starter, verifies the game ID and team identity, and caches prior starts before model asset construction. It can collect up to eight verified earlier starts per pitcher for the targeted pregame sample. A pitcher with fewer than three reliable earlier starts remains a limited-data case.

The selected optional starter correction weight comes from the historical calibration file `outputs/v62_pitcher_calibration.json`. A weight of zero is meaningful—it indicates the selected historical procedure did not support an additional correction. The descriptive 100-based offense/defense/pitching ratings displayed on the page are **not themselves three separate independently calibrated model inputs**. A defensive runs-allowed fallback also contains pitching influence; it is not pure fielding quality.

## What the model does not yet establish

The implementation is **not** pitch-by-pitch and does not prove that each lineup, park, weather or postseason adjustment improves accuracy. Bullpen roster and late lineup information may be partial. New data should be treated as a testable input, not a reason to force a prediction toward the known final score.

For metric definitions and forward-looking validation, see [Validation](VALIDATION.md).
