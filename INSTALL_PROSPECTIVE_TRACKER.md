# MLB Prediction Lab — Prospective Predictions & Kalshi Research Tracker

## Install without losing any 2026 imports

This is an **add-on**, not a replacement project. It assumes your dashboard is already running and you have installed the **Model Uncertainty** add-on (`robust_score_validation.py`).

1. Return to your **Visual Studio Developer PowerShell** and stop Streamlit with **Ctrl+C**.
2. Copy your current `MLB_Backtest_Expanded_2026_Postseason_Markets` folder to a backup location.
3. Extract `MLB_Prediction_Lab_Pregame_Tracker_ADDON.zip`.
4. Copy `prospective_tracker.py`, `test_prospective_tracker.py`, and the included `pages` folder into your existing project folder **alongside** `dashboard.py` and `run_all.py`. When prompted, **merge** `pages` instead of replacing its other pages.
5. **Do not delete or overwrite the `data` folder**, your existing Streamlit dashboard, or `outputs`.
6. Open Developer PowerShell in your existing project directory.

```powershell
py -m unittest discover -q
py -m streamlit run dashboard.py
```

The Streamlit sidebar should now have a page called **Prospective Tracker**. It is normal for the first use to take a few seconds because the scoring model and expanded model may need to fit.

## How to use on October 12, 2026

MLB scheduled **Dodgers @ Brewers at 5:00 PM ET** and **Guardians @ Rays at 8:00 PM ET**. Because the Dodgers game may have already started when you install this, the app **refuses to claim that a new Dodgers forecast was captured before first pitch**. You can still view the pregame-date research probabilities in `Game forecasts` (that screen is not a timestamped prospective record).

For **Guardians @ Rays**, provided it is **still before official first pitch**, open **Prospective Tracker**:

1. Go to **Freeze pregame forecasts**, set **2026-10-12**, choose **Cleveland Guardians at Tampa Bay Rays**, and click **Save official pregame forecast**. The app re-checks official MLB scheduling and timestamps the complete Elo and score-distribution forecasts.
2. If you wish to compare Kalshi pricing, open the **BUY YES order ticket** yourself and obtain the **actual contract ask** and **fee**. A `1.64x` payout multiplier is **not** an executable quote. Enter the ask **in cents for one $1-payout YES contract**, and fee **in cents per contract**, under **Record Kalshi price**. Tick the attestation checkbox, then save.
3. Optionally choose **Paper positions → Lock ONE hypothetical paper contract**. This is explicitly **not an order** and risks **no funds**. No automatic buying or selling is possible.
4. Once the game is officially **Final**, open **Settle & evaluate**, choose the game date, select **Check official FINAL scores and settle**, then **Recalculate prospective validation**.

The local journal is stored in `outputs/prospective/`. It retains frozen input versions, timestamped forecast probability matrices, user-entered quote observations, any voluntarily committed hypothetical paper entries, and official finals. Each JSONL file uses a simple hash chain to detect accidental edits; this is **not** externally notarized evidence.

**It is not possible to retroactively log a pregame prediction after first pitch.** If you miss today's window, use the tracker on future postseason games.

## Optional: automatic local pregame logging

You can run a **separate Developer PowerShell window** with the project as the current directory:

```powershell
py prospective_tracker.py watch --date 2026-10-13 --lead-minutes 60 --interval-seconds 90
```

This **foreground** process checks the official schedule periodically and freezes a game's pregame forecast when it's within 60 minutes of scheduled first pitch. You must keep the terminal **running**; it does **not** continue working when the computer or terminal is closed. It does **not** monitor Kalshi prices or trade. Stop it with **Ctrl+C**. It will stop automatically once the final scheduled first pitch has passed.

To list the official fixtures and game IDs:

```powershell
py prospective_tracker.py list --date 2026-10-12
```

To evaluate recorded predictions manually in PowerShell:

```powershell
py prospective_tracker.py settle --date 2026-10-12
py prospective_tracker.py report
```

## How prices are interpreted

For **one YES contract paying $1 if true**:

- Real quoted BUY YES ask: `55` cents means a $0.55 asking price.
- Estimated **per-contract** fee: `2` cents means another $0.02.
- Total cost if the ask were filled: $0.57.
- Break-even probability at a $1 payout: 57%.
- Model-implied expectation per contract: `model YES probability − 0.57` dollars.

These are **hypothetical** calculations, not evidence of an actual fill, current market availability, or positive expected profit. Kalshi fees can vary by market, price, quantity, and applicable fee schedule: manually enter the applicable fee from your order ticket or official fee disclosure. The app **does not** retrieve live price quotes, and quote observations are stored separately from locked paper positions. No brokerage connection, trading API token, or account information is required or used.

## Model evidence and limitations

- The *winner* baseline is the previously evaluated Elo probability. The expanded pitcher model is saved only if it can be computed and is still labeled research.
- Exact scores and over/under distributions are exploratory and **not demonstrated to outperform a fair market**. Each frozen game stores four candidates: Poisson, 2024-validated negative-binomial, wider negative-binomial, and constant-run negative-binomial.
- Scores are aligned to the Elo winner marginal, so these four distributions are **not independent win models**.
- The tracker uses historical game results dated **strictly before** the selected game's date and re-fetches official scheduling before any new pregame record.
- Paired game-date bootstrap 95% intervals for **winner Brier**, **exact-score log loss**, **total-run CRPS**, and **under-6.5 Brier** are shown only after **at least 30 settled games across 10 days**. Two playoff picks are too few for reliable evidence.
- The program evaluates *hypothetical* paper P&L from manually saved quotes. It does **not** calculate real returns because actual fills and settlement records were not connected.
- MLB schedules can be delayed or corrected. The application conservatively refuses certification after the reported scheduled first pitch or when official status says the game has begun. If the MLB API can't be reached, recording is blocked rather than using stale status.
- Windows must have internet access to contact the official MLB Stats API for schedules and final scores. No results are invented if the API is unavailable.

### Files added

```
MLB_Backtest_Expanded_2026_Postseason_Markets/
├── prospective_tracker.py
├── test_prospective_tracker.py
├── pages/
│   └── Prospective_Tracker.py
└── outputs/
    └── prospective/                  # created after you first save data
        ├── forecasts.jsonl
        ├── quotes.jsonl
        ├── paper_entries.jsonl
        ├── results.jsonl
        ├── prospective_report.json
        └── prospective_graded_games.csv
```

Troubleshooting: If Streamlit says `ModuleNotFoundError: robust_score_validation`, reinstall the previous Model Uncertainty add-on, preserving the `data` directory. If you see `Schedule unavailable`, check connectivity and reopen the page. If you see `First pitch passed`, that's intentional—move to a future game rather than attempting a late snapshot.
