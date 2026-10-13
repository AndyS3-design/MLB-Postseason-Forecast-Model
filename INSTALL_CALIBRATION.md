# MLB Prediction Lab — 2026 Final-Score Calibration Add-on

This add-on evaluates your existing final-score model against **2026 games** and compares it with the same Elo-aligned **constant-runs baseline**. It does **not** change your trained models or place bets.

## Install (Visual Studio Developer PowerShell)

1. Stop Streamlit with **Ctrl+C**.
2. Back up your existing project folder.
3. From this ZIP, copy `score_calibration_2026.py`, `test_score_calibration_2026.py`, and the `pages` folder into your existing `MLB_Backtest_Expanded_2026_Postseason_Markets` folder (beside `run_all.py`). **Keep the `data` folder as it is.**
4. In Developer PowerShell, in that project folder, run:

```powershell
py -m unittest discover -q
py score_calibration_2026.py --as-of 2026-10-12
py -m streamlit run dashboard.py
```

Streamlit should display a new **Score Calibration** page in the sidebar. If it doesn't, visit `http://localhost:8501/Score_Calibration` or restart Streamlit.

The evaluator writes these files:

- `outputs/score_calibration_2026.json` — regular/postseason/combined summary, uncertainty and reliability bins
- `outputs/score_calibration_2026_games.csv` — one record per 2026 game with expected score, top score, actual score, probability, and errors

## What it checks

- **Score errors** per team (lower is better)
- **Exact-score log loss** (lower is better)
- **Top exact-score and displayed winning-score hit rates** (higher is better)
- **Probability calibration** for both the modal exact score and dashboard-displayed favorite-winning score, with Wilson intervals
- **Under 6.5 Brier score** (lower is better)
- **Day-cluster paired bootstrap intervals** for differences versus baseline

The run model is still trained on 2023–24, and uses earlier 2025–26 game results only as chronological **features**. Elo also updates from only earlier dates. Importantly, the current day's runs are not predictors for that same day.

2026 is a stronger out-of-sample test than 2025, but isn't an untouched blind validation of everything (2026 winner model behavior has already been reviewed). No historical Kalshi prices are included, and none of these metrics demonstrates a positive wagering edge.

### If you see `UNAVAILABLE`

Ensure `data/mlb_2026_regular.csv` and `data/mlb_postseason_2023_2026.csv` exist. Run your existing `py ingest_mlb.py --as-of 2026-10-12` if necessary. The calibration script never invents game results.

### Notes

The exact-score distribution is experimental and still makes simplified extra-inning assumptions. A high-confidence exact final score is not possible. The score model and Elo may disagree; the evaluated score matrix is explicitly tilted to match Elo's winner probability.
