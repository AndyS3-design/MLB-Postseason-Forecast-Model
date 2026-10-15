"""Scoreboard winner-aligned exact mode is distinct from the unconditional mode."""
import json
from pathlib import Path
import unittest
import numpy as np
from v4_simulation import summarize
from v6_baseball_totals import half_run_line_probabilities

ROOT=Path(__file__).resolve().parents[1]


class WinnerScorePresentationTests(unittest.TestCase):
    def test_majority_away_pick_beats_unconditional_home_modal_score(self):
        # Home has the single most frequent exact score, but visitors win
        # two-thirds of all simulated games across different winning scores.
        home=np.array([3]*5+[2]*4+[1]*3+[2]*3,dtype=int)
        away=np.array([2]*5+[3]*4+[2]*3+[4]*3,dtype=int)
        out=summarize({'home_final':home,'away_final':away})
        favorite=out['favorite_aligned_score']
        self.assertAlmostEqual(out['home_win_probability'],5/15)
        self.assertEqual((out['v6_display_score']['home'],out['v6_display_score']['away']),(3,2))
        self.assertEqual((favorite['home'],favorite['away']),(2,3))
        self.assertEqual(favorite['winner_side'],'away')
        self.assertAlmostEqual(favorite['probability'],4/15)
        self.assertAlmostEqual(favorite['conditional_probability'],4/10)
        self.assertAlmostEqual(out['representative_score']['probability'],favorite['probability'])
        self.assertAlmostEqual(sum(out['total_pmf'].values()),1.)

    def test_home_majority_and_exact_over_under_not_modified(self):
        home=np.array([3,3,3,3,4,4,5,5,5,1],dtype=int)
        away=np.array([2,2,2,2,3,3,4,4,4,2],dtype=int)
        out=summarize({'home_final':home,'away_final':away})
        favorite=out['favorite_aligned_score']
        self.assertEqual(favorite['winner_side'],'home')
        self.assertGreater(favorite['home'],favorite['away'])
        self.assertAlmostEqual(favorite['probability'],.4)
        self.assertAlmostEqual(favorite['conditional_probability'],.4/.9)
        self.assertAlmostEqual(out['home_win_probability'],.9)
        self.assertEqual(out['total_expected_runs'],float(np.mean(home+away)))
        self.assertEqual(out['under_6_5_probability'],float(np.mean(home+away<=6)))

    def test_historical_oct14_forecast_is_read_only(self):
        path=ROOT/'cloud_records/preliminary_revisions/849811_20261014T202744Z.json'
        if not path.exists():self.skipTest('Archived October 14 preview unavailable')
        frozen=path.read_bytes()
        record=json.loads(frozen)
        self.assertAlmostEqual(record['predicted_home_win'],.46225)
        self.assertAlmostEqual(half_run_line_probabilities(record['total_distribution'])['5.5']['over'],.6475833333,places=5)
        self.assertEqual(record['projected_score']['home'],2)
        self.assertEqual(record['projected_score']['away'],3)
        self.assertEqual(path.read_bytes(),frozen)


if __name__=='__main__':unittest.main()
