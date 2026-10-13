MLB Forecast Lab V6.2 - missing import dependency repair

Cause: V6.2 v6_app/app.py imports 'pregame_history_only' from v6_strength.py, but the V6.2 add-on omitted the updated v6_strength.py and v6_replay.py files from V6.1. This led to ImportError on installations still using an older v6_strength.py.

INSTRUCTIONS (Windows Visual Studio Developer PowerShell):
1. Ctrl+C to stop Streamlit.
2. Back up your existing MLB_Backtest_Expanded_2026_Postseason_Markets folder.
3. Copy BOTH v6_strength.py and v6_replay.py into the ROOT of that project folder, where run_all.py and v62_calibrate.py live. Replace existing versions if asked.
   Do not copy to v6_app or data; do not delete data or outputs.
4. In Developer PowerShell, from your project root:
   py -c "from v6_strength import team_indices, pregame_history_only; from v6_replay import clean_game_input, historical_cutoff_assets; print('V6.2 dependencies OK')"
   py -m unittest discover -q
   py v62_calibrate.py
   py -m streamlit run v6_app/app.py

The dependency repair changes only two Python modules; it does not alter the models' trained weights or data. Historical forecasts remain retrospective research only.
