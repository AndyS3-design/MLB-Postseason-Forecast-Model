"""V6 presentation invariants. No live MLB or betting API calls."""
import unittest
from unittest.mock import patch
from v4_simulation import play_games,summarize
from v6_display import display_forecast


class TestV6Scoreline(unittest.TestCase):
    def test_scoreline_and_total_agree_across_run_profiles(self):
        for i,(home,away) in enumerate([(4.,4.15),(2.,7.),(8.,3.),(1.2,1.4),(5.,5.),(3.2,6.8)]):
            with self.subTest(home=home,away=away):
                draws=play_games(home,away,n=3500,seed=i+41,postseason=True)
                p=summarize(draws)
                d=display_forecast(p,'Away','Home',6.5)
                self.assertEqual(d['total'],d['home_runs']+d['away_runs'])
                self.assertNotEqual(d['home_runs'],d['away_runs'])
                self.assertEqual(d['winner'], 'home' if d['home_runs']>d['away_runs'] else 'away')
                self.assertAlmostEqual(d['over']+d['under']+d['push'],1.0,places=8)
                self.assertTrue(0<=d['chosen_score_probability']<=1)

    def test_integer_line_push(self):
        p=summarize(play_games(3.9,4.2,n=3000,seed=7))
        d=display_forecast(p,'Away','Home',8.)
        self.assertGreater(d['push'],0)
        self.assertAlmostEqual(d['over']+d['under']+d['push'],1,places=8)

    def test_noninteger_line_has_no_push(self):
        p=summarize(play_games(3.,4.,n=3000,seed=8))
        d=display_forecast(p,'Away','Home',7.5)
        self.assertAlmostEqual(d['push'],0)

    def test_missing_replacement_gives_clear_error(self):
        p=summarize(play_games(4.,4.,n=1000))
        del p['v6_display_score']
        with self.assertRaisesRegex(ValueError,'install the updated'):
            display_forecast(p,'Away','Home',6.5)

    def test_tamper_total_detected(self):
        p=summarize(play_games(4.,4.,n=1000))
        p['v6_display_score']['total']+=1
        with self.assertRaisesRegex(ValueError,'total mismatch'):
            display_forecast(p,'Away','Home',6.5)

    def test_tamper_winner_detected(self):
        p=summarize(play_games(4.,4.,n=1000))
        p['v6_display_score']['home'],p['v6_display_score']['away']=(
            p['v6_display_score']['away'],p['v6_display_score']['home'])
        with self.assertRaisesRegex(ValueError,'favored winner disagree'):
            display_forecast(p,'Away','Home',6.5)

    def test_display_does_not_change_probabilities(self):
        p=summarize(play_games(4.,4.,n=3000,seed=7))
        before=(p['home_win_probability'],dict(p['total_pmf']))
        display_forecast(p,'Away','Home',6.5)
        self.assertEqual((p['home_win_probability'],p['total_pmf']),before)

    def test_single_nested_page_only(self):
        from pathlib import Path
        app=Path(__file__).resolve().parent/'v6_app'/'app.py'
        if not app.exists():self.skipTest('V6 app not available in temporary test dir')
        self.assertTrue(app.exists())
        self.assertFalse((app.parent/'pages').exists())

if __name__=='__main__':unittest.main()
