# MLB Forecast Lab — Baseball-only V6.5 patch

This add-on makes the standalone V6/V6.4 dashboard a baseball-only research tool.
It removes the sportsbook / prediction-exchange comparison panel, the odds API connector, entry of market quotes, and the corresponding imports. Your forecast no longer has even a presentation-layer dependency on sportsbook pricing code.

## Windows / Visual Studio

1. Stop the running Streamlit app in Developer PowerShell with `Ctrl+C`.
2. Back up your `MLB_Backtest_Expanded_2026_Postseason_Markets` folder.
3. Extract this ZIP and copy the `v6_app` folder plus `v6_display.py`, `v6_baseball_totals.py` and `test_v65_baseball_only.py` into the existing project. Select **Replace** for `v6_app/app.py` and `v6_display.py`.
4. **Keep your existing `data` and `outputs` folders**. No new API key is needed.
5. In Developer PowerShell run:
   ```powershell
   py -m unittest discover -q
   py -m streamlit run v6_app/app.py
   ```

## What stays

- Official MLB schedule/manual matchups and strict historical-replay cutoffs.
- Starters and ERA effects, bullpen histories, offense/defense/pitching ratings, and postseason context.
- One projected score, team win probability, expected run means, selected run-total threshold, and score heatmap.
- Experimental weather and ballpark scenarios and the V6.4 starter-impact audit.

## What goes

- No sportsbook, odds aggregator, exchange, prediction-market, or player-pick UI in the standalone app.
- No odds API key, price fetching, manual quote entry, fee calculator, or price-derived recommendation.
- Pure run-threshold probabilities are computed in `v6_baseball_totals.py` instead of importing a module that also contained pricing functions.

## Important clarification

For safety and backwards compatibility, this patch does not delete old archived scripts or old pages in the parent project. They are **not loaded by** `v6_app/app.py`; do not launch the legacy `dashboard.py` if you want the clean, baseball-only experience. You may archive unused legacy modules later, after ensuring no other research scripts need them.

No trained weights, historical records, outputs or simulation distributions are modified by this UI separation. Baseball-only means independent of market prices, **not** proof the underlying forecasts are accurate. Retrospective tests are still affected by earlier model-development choices; future locked forecasts remain important.
