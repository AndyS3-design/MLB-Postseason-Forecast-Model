import unittest
from datetime import datetime,timedelta,timezone
from cloud.v8_evaluate import valid_original,summary
class EvaluationTests(unittest.TestCase):
    def record(self,lead=20,revised=False):
        now=datetime(2026,10,13,18,tzinfo=timezone.utc)
        return {'forecast_kind':'revised_pregame' if revised else 'original_pregame',
           'forecast_created_utc':now.isoformat(),'game_start_utc':(now+timedelta(minutes=lead)).isoformat(),
           'official_final':{'away':1,'home':2},'predicted_home_win':.6,'elo_home_win':.5,
           'under_6_5_probability':.55,'expected_runs':{'home':3.,'away':4.,'total':7.},
           'health':{'data_gaps':[],'starter_pitcher_history':{'home':6,'away':8},
                     'lineups_confirmed':{'home':True,'away':True}}}
    def test_only_true_pregame_originals(self):
        self.assertFalse(valid_original(self.record(-2)))
        d=summary([self.record(),self.record(revised=True),self.record(-2)])
        self.assertEqual(d['coverage']['original_forecasts'],1)
        self.assertEqual(d['performance']['n'],1)
        self.assertEqual(d['performance']['winner_brier'],.16)
        self.assertEqual(d['coverage']['both_starters_have_3plus_verified_starts_fraction'],1.)
if __name__=='__main__':unittest.main()
