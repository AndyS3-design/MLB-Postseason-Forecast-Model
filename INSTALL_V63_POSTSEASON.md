# MLB Forecast Lab V6.3 — Postseason Scoring Context

This is an **add-on to an existing working V6.2 project**, not a standalone project.

## What the update changes

- Loads all 11 CSV columns supplied by the user for 2022–2026.
- Uses **runs per TEAM per game**, not runs per two-team contest. In 2026 the reported 3.46 implies a 6.92-run combined *league-average* matchup before matchup-specific adjustments, NOT that all games score 6.92.
- Adds a conservative postseason scoring adjustment to the unified simulation's **team run rates**, so BOTH winner and over/under probabilities come from the adjusted runs.
- Uses only completed past seasons (2022–25) for the historical prior, plus the **2026 early-postseason scoring snapshot only for forecast dates >= October 12, 2026**. The October 11 Game 1 replay CANNOT access the 2026 snapshot.
- Preserves pitcher-specific adjustments from V6.2 when a separate 2024-tuned `outputs/v62_pitcher_calibration.json` exists. Otherwise the pitcher-specific factor remains inactive and is visibly flagged.
- Displays an audit: regulation expected runs before/after postseason context and the date cutoff.
- Adds toggles inside **Model options & data coverage** to compare with/without postseason context and optional eligible 2026 trend.
- Retains reliever %, HR %, HR-sourced runs %, and fastball velocity as audit signals ONLY. Five annual observations are insufficient to fit independent causal coefficients for all of them.

### IMPORTANT: model status
The postseason adjustment is an **experimental scenario**, not a proven improvement to market odds or a validated betting system. It may reduce expected runs for some playoff games; it should NOT automatically forecast every elite-starter duel under. The 2025 retrospective already informed model development. Future recorded pregame forecasts are needed to assess repeatable gain.

## Install on Windows / Visual Studio Developer PowerShell

1. Stop Streamlit with **Ctrl + C**.
2. **Back up** `MLB_Backtest_Expanded_2026_Postseason_Markets`.
3. Unzip `MLB_Forecast_Lab_V63_POSTSEASON_SCORING_FIX.zip`.
4. Copy all `.py` files from the ZIP's root into your project root, **merging** the included `v6_app` and `data` folders. Keep all your existing data, 2026 box scores, and outputs. The included CSV is an *additional* data file.
5. In the project folder, run:

```powershell
py -m unittest discover -q
py v63_report.py
py v63_validate.py --as-of 2026-10-13
```

6. **If you have not calibrated V6.2**, run:

```powershell
py v62_calibrate.py
```

A selected pitching weight of **zero** means historic 2024 data did NOT support extra ace adjustments. Do **not** override this to force an under.

7. Launch:

```powershell
py -m streamlit run v6_app/app.py
```

Choose a playoff game, open **Model options & data coverage**, and compare postseason context ON and OFF. The analysis below the forecast will show the exact effect on regulation-run expectations.

### Game 1 Skubal–Misiorowski replay
For October 11, 2026, the 2026 **early-playoff summary is barred** (published later than the selected replay cutoff), and past official starters are conservative/unverified by default. To investigate a scenario, select **Retrospective what-if: use schedule-listed starters**; this is not a certified saved pregame pick. Inspect the starter audit before interpreting the total.

### Matchup-specific caveats
Your source table is an *annual aggregate*, so it cannot identify individual pitcher effects by itself. Do not stack separate velocity, reliever and home-run suppressions: those variables are correlated and may double-count the same pitching advantage. Individual starter impacts still come from the prior-starts model and must pass its independent validation.

## Audit note and sources

The 2022–2026 seasonal runs/team/game numbers were corroborated in CBS Sports, "Why is offense at historic low in the 2026 MLB playoffs?" (published October 11, 2026): https://www.cbssports.com/mlb/news/offense-historic-low-2026-mlb-playoffs-postseason-trends/ .

MLB's October 2 piece discusses higher strikeouts and stuff quality in playoffs, without validating a unique run multiplier: https://www.mlb.com/news/which-lineups-are-built-to-handle-postseason-pitching .

The *other* columns, including reliever IP%, HR%, and average fastball speeds, are **user-provided, provisional** and not independently sourced in this package. The 2026 record reflects an early playoff snapshot, not the full 2026 postseason.
