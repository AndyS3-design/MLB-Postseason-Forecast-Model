"""The scoreboard must not force an arbitrary rounded-mean scoreline."""
import unittest
import numpy as np
from v4_simulation import summarize
from v6_display import display_forecast

class ScoreDisplayTests(unittest.TestCase):
 def test_modal_winner_consistent_score_is_from_actual_simulations(self):
  # Most repeated exact score 3-2 (total 5); mean total is much higher.
  h=np.array([3,3,3,5,6,6,6,3],dtype=int)
  a=np.array([2,2,2,4,5,1,1,2],dtype=int)
  output=summarize({'home_final':h,'away_final':a})
  score=output['v6_display_score']
  self.assertEqual((score['home'],score['away'],score['total']),(3,2,5))
  self.assertEqual(score['probability'],.5)
  self.assertNotEqual(score['total'],round(output['total_expected_runs']))
  self.assertEqual(score['total'],score['home']+score['away'])
  result=display_forecast(output,'MIL','LAN',6.5)
  self.assertEqual(result['total'],5)
  self.assertAlmostEqual(result['model_mean_total'],output['total_expected_runs'])

 def test_score_is_winner_aligned_and_probabilities_not_overridden(self):
  rng=np.random.default_rng(2026)
  a=rng.poisson(4.2,2000)
  h=rng.poisson(3.1,2000)
  ties=(a==h)
  a[ties]+=1
  x=summarize({'home_final':h,'away_final':a})
  score=x['v6_display_score']
  self.assertEqual(score['home']>score['away'],x['home_win_probability']>=.5)
  self.assertEqual(x['representative_score']['home'],score['home'])
  self.assertEqual(x['representative_score']['away'],score['away'])
  self.assertAlmostEqual(sum(x['total_pmf'].values()),1.)

if __name__=='__main__':unittest.main()
