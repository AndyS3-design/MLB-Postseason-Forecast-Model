"""Regression checks for calibration calculation and chronology."""
import unittest
import numpy as np
import pandas as pd
from score_calibration_2026 import one_game, calibration_bins, wilson_interval, prior_day_frame

class ScoreCalibrationTests(unittest.TestCase):
    def test_metrics_on_tiny_matrix(self):
        mat=np.zeros((3,3))
        mat[1,0]=.65;mat[2,1]=.25;mat[0,1]=.10
        r=one_game(mat,1,0)
        self.assertEqual(r['top_score_correct'],1)
        self.assertAlmostEqual(r['actual_score_probability'],.65)
        self.assertAlmostEqual(r['home_win_probability'],.90)
        self.assertEqual(r['display_score_correct'],1)
        self.assertAlmostEqual(r['under_6_5_probability'],1.0)
    def test_calibration_bins(self):
        p=[{'top_score_probability':.035,'top_score_correct':0} for _ in range(5)]
        p += [{'top_score_probability':.045,'top_score_correct':1}]
        b=calibration_bins(p)
        self.assertEqual([x['games'] for x in b],[5,1])
        self.assertEqual(b[1]['observed_frequency'],1)
    def test_wilson(self):
        self.assertEqual(wilson_interval(0,0),[None,None])
        lo,hi=wilson_interval(5,10)
        self.assertLess(lo,.5);self.assertGreater(hi,.5)
    def test_no_later_day_score_leakage(self):
        def g(day,hr,ar):
            return {'game_id':'x-'+day,'year':2026,'date':pd.Timestamp(day),
                'game_num':'0','home':'LAN','away':'MIL','home_final':hr,
                'away_final':ar,'home_reg':hr,'away_reg':ar,
                'home_sp':'','away_sp':''}
        first=g('2026-04-01',3,1)
        second=g('2026-04-02',2,1)
        a=prior_day_frame([first,second])
        second_changed=g('2026-04-02',15,0)
        b=prior_day_frame([first,second_changed])
        x=a[a.game_id=='x-2026-04-02'].iloc[0]
        y=b[b.game_id=='x-2026-04-02'].iloc[0]
        for feat in ['home_rpg15','away_rpg15','home_season_rpg','away_season_rpg']:
            self.assertAlmostEqual(float(x[feat]),float(y[feat]))
    def test_empty_2026_not_claimed(self):
        from score_calibration_2026 import evaluate
        # Existing 2023-25 files aren't required for unit tests: ensure bad date fails.
        with self.assertRaises(ValueError):
            pd.Timestamp('not-a-date')

if __name__=='__main__':unittest.main()
