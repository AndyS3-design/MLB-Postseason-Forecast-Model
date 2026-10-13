MLB 2026 PITCHING MATCH FIX (data-safe)

Issue: extended_eval.all_games() stores MLB game id='api-824621', while
import_mlb_boxscores.py uses game_id='824621'. Previously the advanced model
could not join them, showing 0/2429 detailed starts in 2026.

1. Stop Streamlit with Ctrl+C.
2. Back up your project folder.
3. Copy matchup_model.py, test_2026_detail_ids.py, verify_2026_pitching.py
   into your EXISTING MLB_Backtest_Expanded_2026_Postseason_Markets folder,
   alongside run_all.py. Replace only matchup_model.py when asked.
   DO NOT replace or delete the data folder.
4. Run:
   py -m unittest discover -q
   py verify_2026_pitching.py
5. If 2026 detail rows = 0, download them using:
   py import_mlb_boxscores.py --start 2026-03-01 --through 2026-10-12 --workers 4
   py verify_2026_pitching.py
6. If joined > 0, rerun:
   py run_all.py
   py -m streamlit run dashboard.py
   In the browser click "Clear dashboard caches" (sidebar).
7. Check "Expanded matchup model" for starter prior detailed starts > 0
   when the nominated pitchers actually have prior starts in this dataset.

The advanced model is still experimental. Better coverage doesn't guarantee
better predictive accuracy. This fix DOES NOT add final-score predictions.
