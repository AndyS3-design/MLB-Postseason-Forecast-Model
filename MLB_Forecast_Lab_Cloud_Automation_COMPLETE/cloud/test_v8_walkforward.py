import unittest
import pandas as pd
import numpy as np
from cloud.v8_walkforward import FILTERS,fit,evaluate
from v4_matchup_core import FEATURES
class WalkTests(unittest.TestCase):
    def test_column_ablation(self):
        self.assertNotIn('opp_sp_era',FILTERS['no_starters'](FEATURES))
        self.assertNotIn('opp_bp_era',FILTERS['no_bullpen'](FEATURES))
        self.assertIn('own_rpg15',FILTERS['no_starters_no_bullpen'](FEATURES))
    def test_validation_metrics(self):
        f=pd.DataFrame({'runs_actual':[1,3], 'year':[2022,2022]})
        m=evaluate(f,[2,2])
        self.assertEqual(m['mae'],1.)
        self.assertEqual(m['team_games'],2)
if __name__=='__main__':unittest.main()
