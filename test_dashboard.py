"""Leakage, price math, schedule parsing, and real-game smoke tests for dashboard."""
import unittest
from datetime import date
from pathlib import Path

from forecast_engine import (forecast, elo_probability, historical_snapshot, parse_schedule,
                             quote_analysis, build_run_fit, TEAM_NAMES)
from extended_eval import all_games


def g(d, home, away, hs, as_, yr=None):
    return {'date':d,'year':yr or int(d[:4]),'game_num':'0','game_type':'R',
            'home':home,'away':away,'home_final':hs,'away_final':as_,
            'home_reg':hs,'away_reg':as_, 'home_sp':'','away_sp':''}


class ForecastSafetyTests(unittest.TestCase):
    def setUp(self):
        self.hist=[g('2025-09-01','MIL','LAN',3,2),
                   g('2025-09-02','MIL','LAN',4,0),
                   g('2025-09-03','LAN','MIL',3,4)]

    def test_same_day_outcomes_do_not_change_prediction(self):
        a=forecast(self.hist,'2025-09-03','LAN','MIL')
        changed=self.hist.copy()+[g('2025-09-03','LAN','MIL',0,20)]
        b=forecast(changed,'2025-09-03','LAN','MIL')
        self.assertEqual(a['home_win_probability'],b['home_win_probability'])
        self.assertEqual(a['past_games_used'],b['past_games_used'])

    def test_future_results_do_not_change_past_probabilities(self):
        a=forecast(self.hist,'2025-09-03','LAN','MIL')
        changed=self.hist+[g('2026-10-12','LAN','MIL',11,0)]
        b=forecast(changed,'2025-09-03','LAN','MIL')
        self.assertEqual(a['home_win_probability'],b['home_win_probability'])

    def test_yesterday_updates_rating_and_offseason_regression(self):
        p_before=forecast(self.hist,'2025-09-02','MIL','LAN')
        p_after=forecast(self.hist,'2025-09-03','MIL','LAN')
        self.assertNotEqual(p_before['home_win_probability'],p_after['home_win_probability'])
        p_2026=forecast(self.hist,'2026-03-26','MIL','LAN')
        self.assertNotEqual(p_after['home_win_probability'],p_2026['home_win_probability'])

    def test_quote_math_includes_fees(self):
        result=quote_analysis(.60,55,1)
        self.assertAlmostEqual(result['expected_value_usd_per_contract'],.04)
        self.assertAlmostEqual(result['break_even_probability'],.56)
        self.assertAlmostEqual(result['loss_usd'],-.56)
        with self.assertRaises(ValueError): quote_analysis(.6,99,2)

    def test_schedule_parses_pitchers_and_real_teams(self):
        payload={'dates':[{'date':'2026-10-12','games':[{
           'gamePk':123,'officialDate':'2026-10-12','gameDate':'2026-10-12T21:00:00Z',
           'status':{'detailedState':'Scheduled'},'gameType':'L',
           'teams':{'home':{'team':{'id':158,'name':'Milwaukee Brewers'},
                             'probablePitcher':{'fullName':'Starter A'}},
                    'away':{'team':{'id':119,'name':'Los Angeles Dodgers'},
                             'probablePitcher':{'fullName':'Starter B'}}}}]}]}
        got=parse_schedule(payload,date(2026,10,12))
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]['home'],'MIL')
        self.assertEqual(got[0]['away'],'LAN')
        self.assertEqual(got[0]['home_pitcher'],'Starter A')
        self.assertEqual(parse_schedule(payload,date(2026,10,11)),[])

    def test_real_game_fixture_smoke(self):
        source=Path(__file__).parent/'data'
        if not (source/'GL2023.TXT').exists():self.skipTest('No Retrosheet data')
        games=all_games(source,True)
        self.assertGreater(len(games),7000)
        fitted=build_run_fit(source)
        result=forecast(games,'2025-10-12','MIL','LAN',fitted)
        self.assertGreater(result['past_games_used'],7000)
        self.assertLess(result['last_completed_date'],date(2025,10,12))
        self.assertGreater(result['under_6_5_probability'],0)
        self.assertLess(result['under_6_5_probability'],1)
        # Make sure adding a future outcome does not affect ANY target probability.
        later=g('2026-10-12','MIL','LAN',25,1)
        result2=forecast(games+[later],'2025-10-12','MIL','LAN',fitted)
        self.assertEqual(result['home_win_probability'],result2['home_win_probability'])
        self.assertEqual(result['under_6_5_probability'],result2['under_6_5_probability'])


if __name__=='__main__':unittest.main()

# The tests above also exercise the actual Retrosheet-trained run estimator.
# The refresh utility is tested independently with an intentionally failing importer.
class RefreshRecoveryTests(unittest.TestCase):
    def test_failed_refresh_restores_original_data_and_cache(self):
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        from data_refresh import refresh,refreshed_today
        with TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';raw=data/'mlb_api_json';raw.mkdir(parents=True)
            cached=raw/'mlb_2026_R_2026-10-01.json';cached.write_bytes(b'old json')
            csv_path=data/'mlb_2026_regular.csv';csv_path.write_bytes(b'old csv')
            with patch('data_refresh.subprocess.run',side_effect=RuntimeError('network offline')):
                with self.assertRaisesRegex(RuntimeError,'network offline'):
                    refresh(root,date(2026,10,12))
            self.assertEqual(cached.read_bytes(),b'old json')
            self.assertEqual(csv_path.read_bytes(),b'old csv')
            self.assertFalse(refreshed_today(root,date(2026,10,12)))

    def test_successful_refresh_writes_marker(self):
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        from data_refresh import refresh,refreshed_today
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            done=SimpleNamespace(returncode=0,stdout='{"2026_regular_games":2430,"postseason_games":150}',stderr='')
            with patch('data_refresh.subprocess.run',return_value=done):
                outcome=refresh(root,date(2026,10,12))
            self.assertTrue(outcome['ok'])
            self.assertTrue(refreshed_today(root,date(2026,10,12)))
