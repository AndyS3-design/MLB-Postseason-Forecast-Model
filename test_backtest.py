import unittest
from datetime import datetime
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from backtest import parse_regulation, make_features, game_probs, ExtraInnings

class TestBacktest(unittest.TestCase):
    def test_regulation_linescore(self):
        self.assertEqual(parse_regulation('000010000'),1)
        self.assertEqual(parse_regulation('00000000(10)'),10)
        self.assertEqual(parse_regulation('00010000x'),1)
        self.assertEqual(parse_regulation('000000000120'),0)

    def test_same_date_games_do_not_leak_results(self):
        from datetime import datetime
        day=datetime(2025,5,2)
        g=dict(date=day,year=2025,game_num='0',away='CLE',home='TBA',
               away_final=2,home_final=3,away_reg=2,home_reg=3,
               away_sp='SP1',home_sp='SP2')
        alternative=dict(g,away_final=18,home_final=19,away_reg=18,home_reg=19)
        other=dict(g,away='NYA',home='BOS',away_sp='SP3',home_sp='SP4')
        xa=make_features([g,other])
        xb=make_features([alternative,other])
        np.testing.assert_allclose(xa.iloc[1][['league_rpg','home_rpg15','away_rpg15']].to_numpy(dtype=float),
                                   xb.iloc[1][['league_rpg','home_rpg15','away_rpg15']].to_numpy(dtype=float))

    def test_game_probability_bounds(self):
        ext=ExtraInnings(.52,np.array([0,.5,.3,.2]),100)
        h,u=game_probs(3.2,3.1,.2,.2,ext)
        self.assertTrue(0<h<1 and 0<u<1)

    def test_features_do_not_read_current_result(self):
        g=dict(date=np.datetime64('2025-04-10').astype('datetime64[ms]').astype(datetime),year=2025,
               game_num='0',away='CLE',home='TBA',away_final=2,home_final=3,
               away_reg=2,home_reg=3,away_sp='SP1',home_sp='SP2')
        def one(second_score):
            prior=dict(g,date=np.datetime64('2025-04-09').astype('datetime64[ms]').astype(datetime),
                       away_final=1,home_final=2,away_reg=1,home_reg=2)
            current=dict(g,away_final=second_score,away_reg=second_score)
            frame=make_features([prior,current])
            return frame.iloc[1][['home_rpg15','away_rpg15','home_sp_allowed','away_sp_allowed']].to_numpy(dtype=float)
        np.testing.assert_allclose(one(1),one(9))

if __name__=='__main__':unittest.main()
