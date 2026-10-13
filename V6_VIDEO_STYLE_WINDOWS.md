# MLB Forecast Lab V6 — Video-inspired scoreboard

This upgrade is based on the TikTok screen recording you provided. The video combines a **single score prediction**, **attack/defense ratings**, and a **score-probability heatmap**. The V6 adaptation keeps the underlying baseball probability model unchanged and avoids treating the probability of a specific score as the probability of a team winning.

## Install on Windows (Visual Studio Developer PowerShell)

1. Close the running Streamlit terminal with **Ctrl+C**.
2. Back up your existing `MLB_Backtest_Expanded_2026_Postseason_Markets` folder.
3. Extract `MLB_Forecast_Lab_V6_VIDEO_INSPIRED_ADDON.zip`.
4. Copy **all top-level `.py` files** from the extracted folder into your project folder. In particular, replace `v4_simulation.py` with the version from this ZIP; it adds the score-heatmap data but does not retrain the model.
5. Copy the **whole `v6_app` folder** into the project folder. Keep the hierarchy `MLB_Backtest_Expanded_2026_Postseason_Markets/v6_app/app.py`.
6. **Do not replace or delete your `data/`, `outputs/`, or `pages/` folders.** Your historical datasets, saved evaluations, and old research pages remain intact.
7. Run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -q
py -m streamlit run v6_app/app.py
```

**IMPORTANT:** Launch `v6_app/app.py`, **not** `dashboard.py`. The nested app opens a separate, clean Streamlit navigation without the old research-page list. The original `dashboard.py` remains fully usable.

The browser normally opens at `http://localhost:8501`. If port 8501 is occupied, Streamlit will print another local URL. End the server with `Ctrl+C`.

## What the screen means

- **One final score** is an *illustrative scenario*: a completed, winner-consistent game outcome drawn from simulated scores and chosen near the mean total. It is not a high-confidence exact-score prediction.
- **Scoreline total** is the sum of the two **displayed integers**, always equal to the predicted score's runs. The **mean of all simulated run totals** is a different statistic, accessible under the technical audit.
- **Team favorite percentage** is the proportion of simulations won by that team. It is NOT the probability of the displayed exact score.
- **Attack index** = a team's recent runs scored per game relative to the historical MLB per-team average, shrunken toward 100 with a modest prior. **Defense index** = inverse recent runs allowed per game relative to that league average (higher means fewer runs conceded). **100 means average**, not perfect. These are descriptive and do NOT alter the trained model.
- **Score heatmap** aggregates the same simulated final scores, including extra innings; rows are home team runs, columns are away team runs. `10+` means 10 or more.
- **O/U probabilities** come from the *full run distribution*, not the one example score. Integer total lines may push; a specific market's rules must be verified.
- **Market quotes:** Hard Rock is the Florida-licensed online sportsbook; other books are *reference prices*, not Florida wagering options. Kalshi contracts require an executable ask and fees. Underdog/PrizePicks player picks are not identical to standard team totals.

## Data quality and limitations

The starting-pitcher data, lineups and bullpen availability cannot be assumed correct just because the app runs. Confirm the matchup inputs, and read the audit for any missing coverage. If no MLB API schedule is available, choose **Manual matchup** for research-only work. Past-game forecasts cannot be represented as newly captured pregame predictions.

The scoring model remains an experimental research model using the previously fitted 2023–2024 data and retrospective evaluation of later seasons. Display changes and 30,000–100,000 simulations do not establish better predictive accuracy or a positive expected return. The headline does not contain actual sports odds or place wagers.

## If something goes wrong

- **`No module named ...`**: run `py -m pip install -r requirements.txt` from inside your project folder.
- **`V6 score metadata missing` or `score_grid`**: you did not replace `v4_simulation.py` with this ZIP's updated version.
- **Old navigation is still visible**: stop Streamlit and launch `py -m streamlit run v6_app/app.py` instead of `dashboard.py`.
- **Lineups unknown**: that is intentionally flagged. The model does not fabricate lineup data.
- **Blank schedule**: verify the date or choose **Manual matchup**; official API access is required for live game discovery.

The `V6_VIDEO_STYLE_SAMPLE.html` file is an **offline illustrative design preview** based on historical, not current, model outputs. It is not connected to game or odds feeds.
