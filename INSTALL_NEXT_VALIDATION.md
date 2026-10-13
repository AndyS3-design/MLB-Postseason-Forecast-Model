# MLB Prediction Lab: uncertainty + fair comparison add-on

This add-on introduces `robust_score_validation.py`, a separate **Model Uncertainty** Streamlit page,
and 6 regression tests. It **does not overwrite** `dashboard.py`, `run_all.py`,
any data files, existing outputs, or existing model modules.

## Windows Visual Studio installation

1. Stop Streamlit with **Ctrl+C** in Developer PowerShell.
2. Backup your working `MLB_Backtest_Expanded_2026_Postseason_Markets` folder.
3. Extract the add-on ZIP and copy `robust_score_validation.py`, `test_robust_score_validation.py`
   and the new `pages/Model_Uncertainty.py` into the corresponding places in your existing project.
   Merge the `pages` directory; **do not delete** `pages/Score_Calibration.py`.
4. Keep `data/` unchanged: it contains your 2026 MLB imports and detailed pitching files.
5. From Developer PowerShell **in your project folder**, run:

```powershell
py -m unittest discover -q
py robust_score_validation.py --as-of 2026-10-12
py -m streamlit run dashboard.py
```

The 2026 backtest may take several minutes, depending on your computer. It writes:

- `outputs/robust_validation_2026.json`
- `outputs/robust_validation_2026_games.csv`

Open **Model Uncertainty** in the Streamlit page navigation. It compares **Elo vs. expanded winner**
on the same game IDs and **Poisson vs. frozen negative binomial vs. wider negative binomial
vs. constant-run baseline** on the same score outcomes.

Optional comparison to 2025 (for historical diagnostics only):

```powershell
py robust_score_validation.py --target-year 2025 --as-of 2026-01-01
```

## What the metrics mean

- **Total runs CRPS**: proper score for the entire predictive total-runs distribution; smaller is better.
- **Team-runs CRPS**: mean of home and away run-distribution CRPS; smaller is better.
- **Exact-score log loss**: penalizes too much confidence in incorrect exact scores; smaller is better.
- **80%/90% predictive interval coverage**: fraction of actual scores inside the stated central interval.
- **Day-resampled 95% interval**: paired bootstrap across game days for a model-minus-baseline
  metric difference; includes zero => no clear separation.
- **Brier score**: squared error of the win or under-6.5 probability; smaller is better.

## What is and is not validated

- Uses **frozen 2023–24 fitted run models**, 2024 dispersion estimates, and 2024-tuned Elo settings.
- Opposing models share the **exact same game IDs**, outcomes, cutoffs, and Elo winner adjustment.
- **Never** updates pregame inputs with the scores from the same calendar day.
- The *expanded winner* comparison incorporates prior starter and bullpen inputs **only when**
  your existing `advanced_pitching_details.csv` and related directory files are present.
- Negative-binomial candidates here test different scoring variances, **not** a newly trained
  or proven better winner model.
- The fixed run model was iteratively developed with past 2025 and 2026 results visible. Those seasons
  are retrospective tests, **not genuinely untouched prospective holdouts**.
- Extra-inning run distribution remains approximate.
- 2026 and playoff results could still be noisy; statistical intervals do not correct all sources of bias.
- **No Kalshi value claims** can be made without timestamped real executable quotes and fees.
- **No model automatically replaces the primary Elo forecast** on the dashboard.

## Troubleshooting

If the script says "No completed target-year games", ensure your original importer succeeded:

```powershell
py ingest_mlb.py --as-of 2026-10-12
```

If the advanced starter coverage is 0, verify the 2026 pitching import and matching:

```powershell
py verify_2026_pitching.py
```

If your terminal says `No module named`, install original project requirements:

```powershell
py -m pip install -r requirements.txt
```

The add-on needs the same NumPy, pandas, SciPy, scikit-learn and Streamlit packages already
used in your working project.
