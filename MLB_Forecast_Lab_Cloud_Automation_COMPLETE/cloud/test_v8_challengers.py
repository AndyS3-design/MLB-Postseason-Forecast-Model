"""Prospective challenger validation uses strictly original pre-first-pitch data."""
import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cloud.v8_challengers import save_shadow_forecasts,attach_shadows,evaluate_pair,variants

UTC=timezone.utc
NOW=datetime(2026,10,13,18,0,tzinfo=UTC)

def game(now=NOW,lead=20):
    return {'id':'700000','date':now.date().isoformat(),'away':'LAN','home':'MIL',
            'game_type':'L','start_utc':(now+timedelta(minutes=lead)).isoformat()}
def original(now=NOW):
    return {'game_id':'700000','date':now.date().isoformat(),'away':'LAN','home':'MIL',
            'game_start_utc':(now+timedelta(minutes=20)).isoformat(),
            'forecast_created_utc':(now+timedelta(seconds=1)).isoformat(),
            'predicted_home_win':.65,'under_6_5_probability':.2,
            'expected_runs':{'total':9.0},'model_version':'test-v8'}
def predict(calls):
    def run(*args,**kwargs):
        calls.append(kwargs.copy())
        if kwargs.get('starter_correction_override')==0:
            return {'forecast':{'home_win_probability':.6,
                     'total_expected_runs':8.0,'under_6_5_probability':.3}}
        if kwargs.get('postseason_context_enabled') is False:
            return {'forecast':{'home_win_probability':.62,
                     'total_expected_runs':9.5,'under_6_5_probability':.15}}
        if kwargs.get('include_2026_snapshot') is False:
            return {'forecast':{'home_win_probability':.61,
                     'total_expected_runs':8.5,'under_6_5_probability':.26}}
        raise AssertionError('Unexpected challenger settings')
    return run
class ChallengerTests(unittest.TestCase):
    def test_pregame_models_separate_from_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);calls=[];initial=original()
            output=save_shadow_forecasts(root,game(),initial,NOW,100,[],game(),{},
                                          generator=predict(calls),clock=lambda:110.)
            self.assertEqual(output['status'],'shadows_saved')
            self.assertEqual(len(calls),3)
            self.assertEqual(calls[0]['starter_correction_override'],0.)
            self.assertFalse(calls[1]['include_2026_snapshot'])
            self.assertFalse(calls[2]['postseason_context_enabled'])
            self.assertEqual(calls[0]['n'],12000)
            self.assertEqual(original(),initial)
            file=root/'cloud_records/challengers/700000.json'
            self.assertTrue(file.exists())
            records=[initial.copy()]
            attach_shadows(records,root)
            self.assertEqual(records[0]['shadow_forecasts']['without_postseason_context']['total_expected_runs'],9.5)
            snapshot=file.read_bytes()
            retry=save_shadow_forecasts(root,game(),initial,NOW,100,[],game(),{},
                                         generator=predict([]),clock=lambda:110.)
            self.assertEqual(retry['status'],'already_frozen')
            self.assertEqual(file.read_bytes(),snapshot)
    def test_live_or_late_challenger_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            out=save_shadow_forecasts(tmp,game(),original(),NOW,100,[],game(),{},
                        generator=predict(calls),clock=lambda:100+22*60.)
            self.assertEqual(out['status'],'insufficient_pregame_window')
            self.assertFalse((Path(tmp)/'cloud_records/challengers/700000.json').exists())
            self.assertEqual(calls,[])
    def test_game_identity_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad=game();bad['home']='CLE'
            out=save_shadow_forecasts(tmp,bad,original(),NOW,100,[],game(),{},
                        generator=predict([]),clock=lambda:110.)
            self.assertEqual(out['status'],'identity_mismatch')
    def test_only_originals_and_pairwise_games(self):
        initial=original()
        initial['official_final']={'home':5,'away':2}
        initial['shadow_forecasts']={
          'without_extra_starter_correction':{'status':'saved',
                'home_win_probability':.60,'total_expected_runs':8.0,
                'under_6_5_probability':.3}}
        result=evaluate_pair([initial])
        value=result['without_extra_starter_correction']
        self.assertEqual(value['n'],1)
        self.assertAlmostEqual(value['winner_brier_main'],.1225)
        self.assertAlmostEqual(value['winner_brier_challenger'],.16)
        self.assertEqual(value['total_mae_main'],2.)
        self.assertEqual(value['total_mae_challenger'],1.)
    def test_regular_season_does_not_add_fake_playoff_variant(self):
        self.assertEqual(len(variants('R')),1)
        self.assertEqual(len(variants('L')),3)
if __name__=='__main__':unittest.main()
