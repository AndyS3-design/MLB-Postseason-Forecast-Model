# MLB Prediction Lab V5 — Windows/Visual Studio install

**Recommended: install the ADD-ON into your already-working `MLB_Backtest_Expanded_2026_Postseason_Markets` project.** Do not delete `data/`, `outputs/`, or existing `pages/`.

## Installation

1. Stop the running Streamlit terminal with **Ctrl+C**.
2. Make a backup copy of the whole project folder.
3. Extract **MLB_Prediction_Lab_V5_TOTALS_MARKETS_ADDON.zip**.
4. Copy the unpacked `.py` files **alongside** `run_all.py` in your current project root. **Replace `v4_simulation.py`** when asked; it supplies the full total-run probability distribution needed by V5. Other V4 scripts are unchanged.
5. Merge the included `pages/` folder with the current `pages/` folder; keep your previous dashboard pages.
6. Keep ALL of your existing `data/`, `outputs/`, and 2026 imports.

In Visual Studio Developer PowerShell in the project folder:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -q
py -m streamlit run dashboard.py
```

The Streamlit sidebar should show **Totals First V5**. Open that page. It is separate from your historical dashboards.

## Use it

1. Choose **Game date** and select a matchup from the **official MLB schedule**.
2. **Before first pitch**, the page attempts to retrieve current MLB pregame lineups/roster from the official feed, if available. Press **Load MLB-verified pregame batting orders and bullpen IDs** for another try. Pregame availability varies; unknown lineups remain **neutral**.
3. Optionally open **Game inputs**. The MLB weather sensitivity is labeled experimental. Historical park proxy also requires checking venue consistency.
4. Press **Generate unified prediction**. The primary display shows **one representative score**, **winner and chance**, **expected total**, **over/under** for **any entered total line**, and each team's expected runs.
5. Expand **Fetch sportsbook / exchange reference prices** to enter your personal *The Odds API* key and retrieve available book prices. This is optional; your model still runs without it. The vendor controls coverage, freshness and plan entitlements. Get access at https://the-odds-api.com/.
6. Check the **exact same market line and rules**. A 6.5 line is NOT interchangeable with 7.5. Only book prices at your selected line are directly displayed for comparison. Odds from aggregation are **indicative reference prices**, not guaranteed buy tickets. Select a different line manually when needed.
7. The panel includes **Hard Rock Bet (FL)**, **DraftKings**, **FanDuel**, **BetMGM**, **Caesars**, **Fanatics**, **BetRivers**, **theScore Bet (formerly ESPN BET)**, and **Kalshi** where the provider feed actually returns data. The provider-coverage table shows names even when quotes aren't available; **no price is fabricated**.
8. **Underdog and PrizePicks** appear in a **separate DFS / player picks panel**: after loading event odds, click the separate **Fetch available player props** button (may consume more API credits). Player props have different terms and payouts and **must not be compared as if they were a game run-total book line**. Some PrizePicks Team Picks are event contracts, but individual availability and settlement must be checked.
9. To compare an actual buy ticket, open **Check Kalshi YES contract or manually entered sportsbook quote**; enter the displayed line and YES ask + estimated fees or American/decimal book odds. Only click **Record...** if the offer was personally observed **before scheduled first pitch**. This records a timestamped **manual observation**, not a wager.
10. Expand **Advanced matchup evidence, model assumptions and validation** to inspect source coverage, limitations and export audit JSON. You can freeze an official pregame simulation; historical games and post-start games cannot be newly logged as prospective pregame forecasts.

## Optional API key across sessions

In a local terminal, for **the current shell only**:

```powershell
$env:ODDS_API_KEY = 'YOUR_KEY_HERE'
py -m streamlit run dashboard.py
```

Do not publish keys, paste them into source code, upload `outputs/` or `.env` to public repositories, or share screenshots containing your key. The key entered in the Streamlit password field stays in your own session and is not included in exported forecast files. Do not share live access keys with ChatGPT.

## Providers vs access in Florida

- **Hard Rock Bet (FL):** Florida's licensed online sportsbook.
- **DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers, theScore Bet:** **research-only reference sportsbook prices** while in Florida; not advertised as available for wagering in Florida.
- **Kalshi:** event-contract exchange, not a Florida-licensed sportsbook; product access and applicable law are distinct from ordinary sportsbook licensing and subject to change.
- **Underdog / PrizePicks:** fantasy and/or prediction products whose state/product availability and rules must be checked. Their player-line entries are not generally comparable to standalone MLB game total odds.

## Honest model limitations

- V5 **does not** download actual executable prices from every platform automatically. The Odds API is an optional third-party provider; most complete feeds are paid/limited by subscription, and sports event coverage varies. With no key, the model uses your own manually supplied quotes.
- Team run rates originate in the 2023–2024 trained V4 historical engine. Pitcher/lineup/roster and weather context overlays are **not demonstrated as calibrated profitable betting features**.
- The single score is the *most common exact score for the model's favored winner*, **not** the expected total rounded and **not** a high-probability outcome. Expected home/away runs are separate and need not add up to that score.
- Only one full-game Monte Carlo is run per match; winner, O/U, team runs and the displayed score are derived from it. This is not an in-game forecasting engine.
- The model includes extra innings approximately. Integer run lines have push probability and may refund stakes depending on venue rules; markets may settle differently. **Check contract terms.**
- Staleness labels apply to aggregator quotes. A green/positive mathematical discrepancy is **not** proof of an edge or instruction to trade.
- No automated betting, order execution, logged real fills, background refresh, or guaranteed real-time availability is provided.
- Use prospectively frozen predictions and independent future outcomes for unbiased calibration testing.

Sources: https://the-odds-api.com/sports-odds-data/bookmaker-apis.html, https://the-odds-api.com/liveapi/guides/v4/, https://www.hardrock.bet/florida/, https://www.prizepicks.com/help-center/eligibility, https://help.underdogsports.com/en/articles/8923390-state-eligibility.
