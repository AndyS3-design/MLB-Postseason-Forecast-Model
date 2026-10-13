"""TikTok-inspired visualization regression tests. No server required."""
import unittest
from datetime import date
from v6_strength import team_indices
from v6_score_grid import heatmap_html,validate_grid
from v4_simulation import play_games,summarize
from v6_display import display_forecast

class TestVideoLayoutMath(unittest.TestCase):
    def test_strength_no_future_results_or_same_day_leakage(self):
        games=[]
        for day in range(1,25):
            games.append({'date':date(2026,9,day),'home':'LAN','away':'MIL','home_final':3,'away_final':4,'game_num':'0'})
        now=team_indices(games,date(2026,9,25),'LAN','MIL')
        games.append({'date':date(2026,9,25),'home':'LAN','away':'MIL','home_final':2000,'away_final':0,'game_num':'0'})
        games.append({'date':date(2026,9,26),'home':'LAN','away':'MIL','home_final':2000,'away_final':0,'game_num':'0'})
        again=team_indices(games,date(2026,9,25),'LAN','MIL')
        self.assertEqual(now,again)
        self.assertGreater(now['teams']['MIL']['attack'],now['teams']['LAN']['attack'])
        self.assertGreater(now['teams']['MIL']['defense'],now['teams']['LAN']['defense'])
    def test_small_sample_unavailable(self):
        g=[{'date':date(2026,8,d),'home':'LAN','away':'MIL','home_final':4,'away_final':3} for d in range(1,4)]
        r=team_indices(g,date(2026,8,6),'LAN','MIL')
        self.assertFalse(r['teams']['LAN']['available'])
        self.assertIsNone(r['teams']['MIL']['defense'])
    def test_simulated_joint_distribution_is_normalized_and_display_consistent(self):
        sim=play_games(4,4.15,n=2500,seed=112)
        pred=summarize(sim)
        cells=validate_grid(pred['score_grid'])
        self.assertAlmostEqual(sum(cells),1.0,places=8)
        rep=display_forecast(pred,'Dodgers','Brewers',6.5)
        self.assertEqual(rep['total'],rep['away_runs']+rep['home_runs'])
        self.assertNotEqual(rep['home_runs'],rep['away_runs'])
        text=heatmap_html(pred['score_grid'],'LA','MIL',(rep['home_runs'],rep['away_runs']))
        self.assertIn('HOME ↓',text)
        self.assertIn('v6-heat-active',text)
        self.assertIn('10+',text)
    def test_unsafe_team_name_html_is_escaped(self):
        pred=summarize(play_games(4,3,n=1000,seed=3))
        text=heatmap_html(pred['score_grid'],'<img src=x>','Team')
        self.assertNotIn('title="Team 0 · <img',text)
        self.assertIn('&lt;img src=x&gt;',text)
    def test_invalid_heatmap_denied(self):
        with self.assertRaises(ValueError):validate_grid({'cells':[[.0]*11]*11})
if __name__=='__main__':unittest.main()
