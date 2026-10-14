"""V13 playoff run calibration tests: exact 2020–2025 archives, no future results."""
from __future__ import annotations
import csv,shutil,tempfile,unittest
from pathlib import Path
from cloud.v13_postseason_context import (
  context_for_game,with_context_rates,REG_RUNS_COMBINED,
  STRENGTH,PRIOR_EQUIVALENT_GAMES)
from cloud.worker import ROOT

class PostseasonContextTests(unittest.TestCase):
 def test_real_archive_covers_every_season_2020_to_2025(self):
  x=context_for_game('2026-10-14','L',ROOT)
  self.assertTrue(x['active'])
  self.assertEqual(x['completed_years_used'],list(range(2020,2026)))
  self.assertEqual(x['historic_games_used'],261)
  self.assertEqual(x['current_prior_games_used'],29)
  self.assertGreater(x['adaptive_weight'],0)
  self.assertLess(x['factor'],.89)
  self.assertGreater(x['factor'],.7)
  self.assertEqual(x['context_strength'],STRENGTH)
  self.assertEqual(x['prior_equivalent_games'],PRIOR_EQUIVALENT_GAMES)

 def test_no_postseason_adjustment_in_regular_season(self):
  x=context_for_game('2026-10-14','R',ROOT)
  self.assertFalse(x['active'])
  self.assertEqual(with_context_rates(4.,5.,x),(4.,5.))

 def test_multiplier_affects_both_teams_without_swapping_favorite(self):
  x=context_for_game('2026-10-14','L',ROOT)
  a,b=with_context_rates(4.,5.,x)
  self.assertAlmostEqual(a/4,b/5)
  self.assertLess(a+b,9.)

 def test_2026_not_used_as_completed_historical_season(self):
  x=context_for_game('2026-09-29','L',ROOT)
  self.assertEqual(x['current_prior_games_used'],0)
  self.assertEqual(x['completed_years_used'],list(range(2020,2026)))
  self.assertEqual(x['adaptive_weight'],0.)
  y=context_for_game('2026-10-14','L',ROOT,include_2026_snapshot=False)
  self.assertEqual(y['current_prior_games_used'],0)
  self.assertNotEqual(y['factor'],context_for_game('2026-10-14','L',ROOT)['factor'])

 def test_future_or_same_day_scores_never_enter_own_forecast(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'data').mkdir()
   shutil.copy(ROOT/'data/official_postseason_2020_2025.csv',
               root/'data/official_postseason_2020_2025.csv')
   with (root/'data/mlb_2026_regular.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['year','away_final','home_final'])
    w.writeheader()
    for _ in range(550):w.writerow({'year':2026,'away_final':4,'home_final':5})
   with (root/'data/mlb_postseason_2023_2026.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['game_id','date','year','game_type','away_final','home_final'])
    w.writeheader()
    for gid,day,runs in [('1','2026-10-13',2),('2','2026-10-14',30),
                          ('3','2026-10-15',45)]:
     w.writerow({'game_id':gid,'date':day,'year':2026,'game_type':'L',
                 'away_final':runs-1,'home_final':1})
   x=context_for_game('2026-10-14','L',root)
   self.assertEqual(x['current_prior_games_used'],1)
   self.assertEqual(x['current_prior_runs_per_team_game'],1.)
   y=context_for_game('2026-10-15','L',root)
   self.assertEqual(y['current_prior_games_used'],2)
   self.assertGreater(y['factor'],x['factor'])

 def test_changing_model_version_is_not_called_a_fresher_lineup_win(self):
  from cloud.two_stage import paired_stage_metrics
  import json
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   early={'game_id':'700','date':'2026-10-14','home':'LAN','away':'MIL',
          'forecast_kind':'preliminary_pregame',
          'game_start_utc':'2026-10-15T00:00:00+00:00',
          'forecast_created_utc':'2026-10-14T19:00:00+00:00',
          'model_version':'7.0.0-pregame-recency-weighted',
          'expected_runs':{'total':7.82},'predicted_home_win':.47}
   final={**early,'forecast_kind':'original_pregame',
          'forecast_created_utc':'2026-10-14T23:40:00+00:00',
          'model_version':'13.0.0-recent-postseason-scoring',
          'official_final':{'home':3,'away':1}}
   for folder,payload in [('preliminary',early),('predictions',final)]:
    dest=root/'cloud_records'/folder/'700.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(payload))
   result=paired_stage_metrics(root)
   self.assertEqual(result['paired_settled_games'],0)
   self.assertEqual(result['excluded_model_version_mismatch'],1)

 def test_without_archive_is_neutral_instead_of_fabricating_data(self):
  with tempfile.TemporaryDirectory() as d:
   result=context_for_game('2026-10-14','L',d)
   self.assertEqual(result['factor'],1)
   self.assertFalse(result['active'])

if __name__=='__main__':unittest.main()
