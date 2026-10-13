# MLB Forecast Lab V6.2 — Starting Pitchers Should Affect TOTAL RUNS

## What was actually wrong?

The original `v4_simulation.py` weighted innings differently based on the starter
and the bullpen, then divided those weights by their sum. As a result, a 1.8 ERA
starter and a 4.35 ERA starter could receive nearly identical **game-total run
expectations**: their ERA mostly changed **when** runs occurred, not **how many**
runs were expected. The upstream Poisson model included an opponent starter ERA
feature, but could be insensitive when pitching-history coverage was poor.

V6.2 corrects that using a separate, visible **total-rate adjustment** before
simulating innings. It compares the original conditional Poisson run prediction
to a neutral-starter counterfactual, and applies the opposing starter's actual
**previously observed** smoothed ERA, expected innings, and historical-sample
coverage. The correction has an intensity parameter selected using 2024
validation only. It NEVER learns from the selected game's final score.

This is a research model; using more stats is not itself proof of improved
accuracy, and a great starter does not guarantee an under.

## Install without disturbing saved data

1. Exit Streamlit with Ctrl+C in Developer PowerShell.
2. Back up the current project folder.
3. Extract this ZIP; **copy the Python files into your existing**
   `MLB_Backtest_Expanded_2026_Postseason_Markets` project directory, preserving
   `v6_app/app.py` subfolder structure. Replace `v4_workflow.py`,
   `v4_sources.py`, and `v6_app/app.py` when asked.
4. **Do NOT replace `data/`, `outputs/`, or your other `pages/` tools.**

Run in Developer PowerShell from the project directory:

```powershell
py -m unittest discover -q
py v62_calibrate.py
py -m streamlit run v6_app/app.py
```

`v62_calibrate.py` requires the `data/advanced_pitching_details.csv` that you
already generated with:

```powershell
py import_retrosheet_details.py --years 2023 2024 2025
```

If this CSV is unavailable, the calibrator will refuse to generate a correction.
It does not create invented pitching stats.

The calibrator chooses a correction weight from **0, 0.25, 0.5, 0.75, 1** using
2024 games, starting with a 2023-trained model. It then reports its performance
on 2025 as a **diagnostic**, not a model-selection period. The generated
`outputs/v62_pitcher_calibration.json` is read automatically by the dashboard.

**Important:** If 2024 selects a weight of **0**, the evidence does not justify
applying the new correction automatically. The dashboard will say so. This is a
legitimate test result, not a broken installation. Future prospective games are
needed before treating any nonzero weight as reliable for betting.

## Test the Dodgers–Brewers 2026 NLCS Game 1 example

1. Launch `v6_app/app.py`.
2. Choose game date **October 11, 2026** and Dodgers @ Brewers.
3. Expand **Model options & data coverage**.
4. For a historical research scenario, check **Retrospective what-if: use
   schedule-listed starters** if the MLB schedule shows Tarik Skubal (Dodgers)
   and Jacob Misiorowski (Brewers). It uses retrospective starter identities;
   this is **NOT a genuine pregame backtest** unless those starter IDs were saved
   before first pitch.
5. Click **Run matchup forecast**.
6. Review the **Starter-adjustment evidence & calibration** expander, which
   reports starter histories, ERA, expected innings, original rate, neutral
   counterfactual rate, and adjusted rate for EACH team's projected runs.

The program **does not** input Game 1's final score into the October 11 forecast.
Do not tune the starter strength to recreate the known 2–1 final result.

## What the V6.2 model does and does not validate

- **Does:** use past-only starter history, explicit missing-data warnings, a
  2024-only model selection, a separate 2025 diagnostic, and the existing single
  score/scoreline-total presentation.
- **Does:** display whether each opponent starting pitcher actually changes
  the expected run total. No silent neutral projections.
- **Does not:** guarantee low-run outcomes or an edge against betting markets.
- **Does not:** use any unsupported quote as an executable Kalshi/Hard Rock bet.
- **Does not:** improve historical box-score coverage itself; run the importers.
- **Does not:** automatically incorporate a pitcher from a finished game unless
  you explicitly select the **historical what-if** scenario.

## Troubleshooting

**Zero adjusted pitcher histories:** Confirm the schedule shows the correct
starters and the data cache has their prior starts. For a completed game the
app **deliberately omits** postgame-listed starter IDs unless you enable the
historical what-if scenario.

**`py v62_calibrate.py` refuses calibration:** Run the existing Retrosheet
pitching importer and check that `advanced_pitching_details.csv` exists.

**Selected weight is 0:** The observed 2024 data did not support increasing
starter sensitivity with this method. Keep the older baseline, and improve the
starter forecasting method prospectively instead of forcing lower totals.

**The card ERA differs slightly from the model ERA:** They now use the same
prior and last-eight-start window, but the card still clamps extreme ERAs and
can carry starts across the year boundary while the training features reset
seasonally. The audit identifies which values were used by the model.

Code tests in this environment: **144 passing unit tests**. Full historical
2023–2025 calibration must run on your computer because the detailed pitching
CSV you imported there is not part of this add-on.
