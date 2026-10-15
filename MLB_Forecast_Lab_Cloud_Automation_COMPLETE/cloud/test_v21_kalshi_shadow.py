"""Prospectively saved per-line shadow odds; strict SAME-game scoring."""
import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from cloud.v8_challengers import save_shadow_forecasts,attach_shadows,evaluate_pair

UTC=timezone.utc
NOW=datetime(2026,10,16,17,0,tzinfo=UTC)

def actual_original():
    return {'game_id':'12345','date':'2026-10-16','home':'LAN','away':'MIL',
        'game_start_utc':(NOW+timedelta(minutes=24)).isoformat(),
        'forecast_created_utc':(NOW+timedelta(seconds=1)).isoformat(),
        'model_version':'18.0.0-forecast-integrity',
        'predicted_home_win':.6,'expected_runs':{'total':6.5},
        'under_6_5_probability':.5,
        'total_distribution':{'4':.25,'5':.5,'8':.25}}

def match():
    return {'id':'12345','date':'2026-10-16','home':'LAN','away':'MIL',
        'game_type':'L','start_utc':(NOW+timedelta(minutes=24)).isoformat()}

def stub_model(*args,**kwargs):
    return {'forecast':{'home_win_probability':.62,
        'total_expected_runs':7.2,'under_6_5_probability':.6,
        'total_pmf':{4:.3,5:.2,8:.5}}}

class KalshiShadowTests(unittest.TestCase):
    def test_independent_4_5_5_5_true_pregame_and_later_paired_brier(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=actual_original()
            report=save_shadow_forecasts(root,match(),original,NOW,10.,[],match(),{},
                generator=stub_model,clock=lambda:11.)
            self.assertEqual(report['status'],'shadows_saved')
            raw=json.loads((root/'cloud_records/challengers/12345.json').read_text())
            self.assertEqual(len(raw['variants']),4)
            for item in raw['variants'].values():
                self.assertAlmostEqual(item['under_4_5_probability'],.3)
                self.assertAlmostEqual(item['under_5_5_probability'],.5)
            before=(root/'cloud_records/challengers/12345.json').read_bytes()
            original['official_final']={'home':4,'away':3} # 7 runs, both Unders lose
            attach_shadows([original],root)
            result=evaluate_pair([original])['without_postseason_context']
            self.assertEqual(result['n'],1)
            self.assertEqual(result['total_market_pairs']['4.5']['n'],1)
            self.assertAlmostEqual(result['total_market_pairs']['4.5']['under_brier_main'],.0625)
            self.assertAlmostEqual(result['total_market_pairs']['4.5']['under_brier_challenger'],.09)
            self.assertAlmostEqual(result['total_market_pairs']['5.5']['under_brier_main'],.5625)
            self.assertAlmostEqual(result['total_market_pairs']['5.5']['under_brier_challenger'],.25)
            self.assertEqual((root/'cloud_records/challengers/12345.json').read_bytes(),before)

    def test_old_shadow_does_not_inflate_new_market_comparison(self):
        o=actual_original()
        o['official_final']={'home':4,'away':3}
        o['shadow_forecasts']={'old':{'status':'saved',
            'home_win_probability':.45,
            'total_expected_runs':7.0,'under_6_5_probability':.35}}
        report=evaluate_pair([o])['old']
        self.assertEqual(report['n'],1)
        self.assertEqual(report['total_market_pairs']['4.5']['n'],0)
        self.assertIsNone(report['total_market_pairs']['4.5']['under_brier_main'])
        self.assertEqual(report['total_market_pairs']['5.5']['n'],0)

    def test_invalid_pmf_never_saved_and_original_stays_unchanged(self):
        def broken(*args,**kwargs):
            q=stub_model(*args,**kwargs)
            q['forecast']['total_pmf']={4:.7,5:.7}
            return q
        with tempfile.TemporaryDirectory() as d:
            original=actual_original()
            untouched=json.dumps(original,sort_keys=True)
            reply=save_shadow_forecasts(d,match(),original,NOW,10.,[],match(),{},
                generator=broken,clock=lambda:11.)
            self.assertEqual(reply['status'],'shadow_failed')
            self.assertFalse((Path(d)/'cloud_records/challengers/12345.json').exists())
            self.assertEqual(json.dumps(original,sort_keys=True),untouched)

if __name__=='__main__':unittest.main()
