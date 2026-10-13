"""V6.2 focused tests: historical independence, starter exposures, and UI contract."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from v62_pitching import (
    starter_total_factor, blended_rates, neutralize_starters,read_calibration,
    apply_to_base, calibrate_from_rows, STARTER_FEATURE_NEUTRAL)

class FakePipeline:
    def predict(self,x):
        arr=np.asarray(x)
        # Team environment captures a strong batting team; opponent SP ERA
        # moderately shifts the conditional expectation.
        return 4.8+.12*(arr[:,0]-4.3)
class FakeFit:
    features=['opp_sp_era','opp_sp_innings','opp_sp_known','opp_sp_rest']
    pipeline=FakePipeline()

def frame(era,known=8,ip=6):
    return pd.DataFrame([dict(opp_sp_era=era,opp_sp_innings=ip,opp_sp_known=known,opp_sp_rest=5)])

class PitcherEffects(unittest.TestCase):
    def test_no_starter_history_is_neutral(self):
        self.assertEqual(starter_total_factor(1.5,7,0),1.0)
        self.assertEqual(starter_total_factor(1.5,7,2),1.0)
        p,c,n,f=blended_rates(FakeFit(),frame(1.5,0),1.0)
        self.assertAlmostEqual(p[0],c[0])

    def test_ace_and_weak_starters_have_opposite_effect(self):
        fit=FakeFit()
        ace,c,n,fac=blended_rates(fit,frame(1.9),1.0)
        weak,cw,nw,fw=blended_rates(fit,frame(6.0),1.0)
        self.assertLess(ace[0],weak[0])
        self.assertLess(ace[0],n[0])
        self.assertGreater(weak[0],nw[0])
        self.assertLess(fac[0],1.0)
        self.assertGreater(fw[0],1.0)

    def test_seven_innings_stronger_impact_than_four(self):
        self.assertLess(starter_total_factor(1.8,7,8),starter_total_factor(1.8,4,8))

    def test_zero_strength_is_exact_v4_baseline(self):
        p,c,n,f=blended_rates(FakeFit(),frame(1.8),0)
        self.assertEqual(p[0],c[0])

    def test_monotone_strength_and_no_double_count(self):
        vals=[blended_rates(FakeFit(),frame(1.8),x)[0][0] for x in [0,.25,.5,1.]]
        self.assertEqual(vals,sorted(vals,reverse=True))
        # The neutral-rate estimate is independent of the named starter.
        a=neutralize_starters(frame(1.8)).iloc[0]
        b=neutralize_starters(frame(6.0)).iloc[0]
        self.assertEqual(a['opp_sp_era'],b['opp_sp_era'])

    def test_calibration_loading_is_protected(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'pitch.json'
            self.assertIsNone(read_calibration(path))
            path.write_text(json.dumps(dict(version='6.2-starter-rate-2024-selected',
                    selected_weight=.75,observed_starter_coverage_2024=1500)))
            self.assertEqual(read_calibration(path)['selected_weight'],.75)
            path.write_text(json.dumps(dict(version='other',selected_weight=1.0)))
            with self.assertRaises(ValueError):read_calibration(path)

    def test_feature_audit_is_explicit(self):
        base={'home_features':frame(1.9).iloc[0].to_dict(),
              'away_features':frame(6.0).iloc[0].to_dict()}
        p_h,p_a,audit=apply_to_base(base,FakeFit(),.75)
        self.assertLess(p_h,p_a)
        self.assertTrue(audit['home']['starter_applied'])
        self.assertEqual(audit['home']['prior_starts_with_details'],8)

    def test_calibration_requires_real_starter_coverage(self):
        small=pd.DataFrame({'year':[2023,2024,2025], 'game_type':['R']*3})
        with self.assertRaises(ValueError):calibrate_from_rows(small)

    def test_future_day_source_excluded_when_calibrating(self):
        # The feature-generation system is responsible for cutoff; this check
        # prevents the new helper from ever depending on actual game scores.
        a=frame(1.8);a['runs_actual']=1
        b=a.copy();b['runs_actual']=15
        self.assertEqual(blended_rates(FakeFit(),a,1.0)[0][0],
                         blended_rates(FakeFit(),b,1.0)[0][0])

if __name__=='__main__':unittest.main()

class PitcherCardConsistency(unittest.TestCase):
    def test_card_uses_same_shrinkage_as_historical_model(self):
        from v4_sources import pitcher_snapshot
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'advanced_pitching_details.csv'
            f.write_text('date,pitcher_id,sp_outs,sp_er\n'
                '2026-09-01,MLB-20,18,0\n'
                '2026-09-08,MLB-20,21,3\n'
                '2026-09-15,MLB-20,18,0\n')
            p=pitcher_snapshot(d,'MLB-20','2026-10-01')
            expected=(3*27+18*4.3)/(57+18)
            self.assertAlmostEqual(p['era'],expected,places=3)
