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
  self.assertEqual((score['home'],score['away']),
                   (x['modal_exact_scores'][0]['home'],x['modal_exact_scores'][0]['away']))
  self.assertAlmostEqual(score['probability'],x['modal_exact_scores'][0]['probability'])
  self.assertAlmostEqual(sum(x['total_pmf'].values()),1.)

 def test_single_most_likely_score_can_favor_underdog(self):
  # Home wins the modal exact 3-2 result five times, but the visitors
  # win ten of fifteen simulations by several *different* scores.
  h=np.array([3]*5+[2]*4+[1]*3+[2]*3,dtype=int)
  a=np.array([2]*5+[3]*4+[2]*3+[4]*3,dtype=int)
  out=summarize({'home_final':h,'away_final':a})
  self.assertAlmostEqual(out['home_win_probability'],5/15)
  self.assertEqual((out['v6_display_score']['home'],out['v6_display_score']['away']),(3,2))
  self.assertAlmostEqual(out['v6_display_score']['probability'],5/15)
  self.assertEqual((out['representative_score']['home'],out['representative_score']['away']),(2,3))
  displayed=display_forecast(out,'Brewers','Dodgers',6.5)
  self.assertEqual(displayed['winning_team'],'Brewers')
  self.assertEqual(displayed['displayed_score_winner'],'Dodgers')
  self.assertFalse(displayed['displayed_score_matches_model_favorite'])
  self.assertAlmostEqual(sum(out['total_pmf'].values()),1.)

if __name__=='__main__':unittest.main()
