# MLB Prediction Dashboard — Windows / Visual Studio setup

This add-on expands the **existing, working** `MLB_Backtest_Expanded_2026_Postseason_Markets` project. It does **not** replace your imported 2026 files, which remain in `data/`.

## Install directly into the project you already ran successfully

1. Download `MLB_Prediction_Dashboard_ADDON.zip` and extract it.
2. Copy the files inside the extracted folder **into the same existing folder as `run_all.py`**. It should have `backtest.py`, `extended_eval.py`, `ingest_mlb.py`, `data/`, and now `dashboard.py`, `forecast_engine.py`, `data_refresh.py` and `test_dashboard.py`.
3. If Windows asks whether to replace `requirements.txt`, choose **Replace**. This only adds Streamlit to the original dependencies.
4. In **Visual Studio** (the IDE you showed in your screenshots), open **View → Terminal** or **View → Other Windows → Terminal**. Make sure the terminal's working directory is your project folder.
5. Run the following commands **one at a time**:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -q
py -m streamlit run dashboard.py
```

The app should open in your browser, usually at `http://localhost:8501`. Leave the Developer PowerShell terminal open while using the dashboard; press **Ctrl+C** in the terminal when finished.

**Important:** Your PC recognizes the command `py`, not `python`; use `py` in every command. You do **not** need to activate a virtual environment or change your PowerShell execution policy.

If Streamlit asks for an email address the first time, you may press Enter to skip.

## Use the app

- **Game forecasts:** Select a date and choose an official scheduled game. If fetching the schedule fails, choose a manual matchup. The dashboard shows each team's **Elo win probability**. It also shows experimental under/over 6.5 probabilities when the totals toggle is on.
- **Starting pitchers:** Probable starters are displayed as context if provided by the MLB schedule feed. **The probabilities do not incorporate individual starting pitchers, projected lineups, injuries, or bullpen availability.**
- **Kalshi price check:** Select a contract and enter the current executable **YES ask in cents**, plus the applicable **fee in cents**. The model shows break-even probability and expected value for one $1 payout contract. It does **not** connect to Kalshi or place trades.
- **Backtest:** Inspect existing historical metrics and optionally upload actual timestamped, pregame executable Kalshi quotes to evaluate the historical trading strategy. Quotes are not included.

## How automatic updating works

The **Auto-refresh on first visit each day** switch is on by default. When you open the dashboard during 2026, it attempts to update the completed MLB games **through the previous calendar date**; it never uses results from the selected game date to forecast that game. This is **not** a background scheduler, and it only runs when the dashboard is opened. If a download fails, earlier working source CSV and cached JSON files are restored.

Use the sidebar button **Refresh 2026 completed results now** for an immediate retry. The latest month's JSON is re-downloaded, since the original project otherwise reuses a potentially stale monthly cache. MLB API access and Internet are required for live updating.

If your computer blocks MLB's API, the dashboard still supports **manual team selection using whatever historical games you already downloaded**. A stale-data warning should be treated seriously.

## Forecast integrity and limitations

- The **Elo winner** model uses fixed previously tuned parameters: `K=8`, `HOME_ELO=20`, and yearly carryover `.75`. It computes ratings from every completed historical game strictly **before** the selected game date. On-date and future final scores are excluded, even for doubleheaders.
- The **experimental 6.5-run model** is trained exclusively on 2023–2024 regular seasons and includes a statistical extra-inning estimate. It has not demonstrated a dependable historical pricing edge; it should not be relied on to bet. Missing regulation runs from *earlier* archived games are approximated using final runs, a known limitation.
- Historic scores and starters can be revised by source providers. Adding **older** games may change later predictions without involving future-data leakage. Adding **newer** games cannot change forecasts for dates before them; this is tested.
- The model is **not** live or in-game. Probabilities do not change with inning-by-inning game state.
- 2026 data requires `data/mlb_2026_regular.csv` and `data/mlb_postseason_2023_2026.csv`, imported by the existing script. If you extracted the complete alternative project, you must refresh 2026 or copy your current imported CSVs.
- Historical profitability is **unknown** until actual executable, timestamped Kalshi prices and fees have been supplied. Even positive modeled expected value is not a guarantee of profit.

## Troubleshooting

**`No module named streamlit`**: run `py -m pip install -r requirements.txt` in the correct folder.

**`Python was not found`**: use `py`, not `python`, just as you did in your prior successful backtest.

**Missing historical files**: verify `data/GL2023.TXT`, `data/GL2024.TXT`, `data/GL2025.TXT` are present in the same project folder.

**MLB schedule cannot load**: use the manual team selector. All data calculations can still run offline with existing historical data.

**New version produced a different probability**: inspect the selected date and **latest included game date**. If either the history or date changes, the probability can change. Verify the model tests with `py -m unittest discover -q`.

## Data attribution

Retrosheet game logs: information obtained free of charge from and copyrighted by Retrosheet (www.retrosheet.org). MLB schedule/game records: MLB Stats API.
