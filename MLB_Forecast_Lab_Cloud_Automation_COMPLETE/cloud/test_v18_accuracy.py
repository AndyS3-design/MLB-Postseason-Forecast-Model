"""Prospective accuracy requires frozen originals and independent game dates."""
import json,tempfile,unittest
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from cloud import worker

UTC=timezone.utc


def original(game_id=1,day=0,delta=.09):
    start=datetime(2026,9,1,23,tzinfo=UTC)+timedelta(days=day)
    return {'game_id':str(game_id),'date':start.date().isoformat(),
            'home':'MIL','away':'LAN','forecast_kind':'original_pregame',
            'forecast_created_utc':(start-timedelta(minutes=20)).isoformat(),
            'game_start_utc':start.isoformat(),
            'official_final':{'home':3,'away':2},
            'predicted_home_win':.6,'elo_home_win':.5,
            'expected_runs':{'home':3.,'away':2.,'total':5.},
            'under_6_5_probability':.7,
            'evaluation':{'correct_winner':True,'winner_brier':.16,
                          'elo_brier':.16+delta,'abs_run_error_per_team':1.,
                          'under_6_5_brier':.09}}


class ProspectiveAccuracyTests(unittest.TestCase):
    def assert_no_interval(self,result):
        self.assertNotIn('elo_minus_model_brier_95_ci',result)
        self.assertNotIn('statistically_distinguishable_from_elo',result)
        self.assertNotEqual(result['status'],'Confidence interval available')

    def test_thirty_games_on_one_or_two_dates_do_not_establish_significance(self):
        for days in (1,2):
            with self.subTest(days=days):
                result=worker.prospective_metrics([original(i,i%days) for i in range(30)])
                self.assertEqual(result['settled_games'],30)
                self.assertEqual(result['settled_dates'],days)
                self.assert_no_interval(result)
                self.assertIn('independent dates',result['status'])

    def test_fewer_than_thirty_games_on_ten_dates_still_waits(self):
        result=worker.prospective_metrics([original(i,i%10) for i in range(29)])
        self.assertEqual(result['settled_dates'],10)
        self.assert_no_interval(result)

    def test_unsettled_dates_do_not_count_toward_uncertainty_interval(self):
        records=[original(i,i%2) for i in range(30)]
        for day in range(2,12):
            pending=original(100+day,day)
            pending.pop('evaluation');pending.pop('official_final')
            records.append(pending)
        result=worker.prospective_metrics(records)
        self.assertEqual(result['settled_games'],30)
        self.assertEqual(result['settled_dates'],2)
        self.assert_no_interval(result)

    def test_thirty_games_on_ten_dates_produce_deterministic_cluster_interval(self):
        records=[original(i,i%10,delta=.02+.01*(i%10)) for i in range(30)]
        result=worker.prospective_metrics(records)
        self.assertEqual(result['settled_games'],30)
        self.assertEqual(result['settled_dates'],10)
        self.assertEqual(result['status'],'Confidence interval available')
        lo,hi=result['elo_minus_model_brier_95_ci']
        self.assertGreater(lo,0)
        self.assertLess(lo,hi)
        self.assertTrue(result['statistically_distinguishable_from_elo'])
        self.assertEqual(worker.prospective_metrics(list(reversed(records))),result)

    def test_valid_legacy_original_stays_eligible(self):
        record=original()
        record.pop('forecast_kind')
        result=worker.prospective_metrics([record])
        self.assertEqual(result['settled_games'],1)
        self.assertEqual(result['accuracy'],1)
        self.assertEqual(result['winner_brier'],.16)
        self.assertEqual(result['elo_brier'],.25)
        self.assertEqual(result['run_mae_per_team'],1)
        self.assertEqual(result['under_6_5_brier'],.09)
        self.assert_no_interval(result)

    def test_late_naive_malformed_and_nonoriginal_records_are_excluded(self):
        records=[original()]
        for kind in ('revised_pregame','preliminary_pregame','lineup_confirmed_pregame'):
            records.append({**original(),'forecast_kind':kind})
        for idx,created,start in (
                (2,'2026-09-01T23:00:00Z','2026-09-01T23:00:00Z'),
                (3,'2026-09-01T23:01:00Z','2026-09-01T23:00:00Z'),
                (4,'2026-09-01T22:40:00','2026-09-01T23:00:00Z'),
                (5,'not a timestamp','2026-09-01T23:00:00Z'),
                (6,'2026-09-01T22:40:00Z','bad start')):
            records.append({**original(idx),'forecast_created_utc':created,'game_start_utc':start})
        result=worker.prospective_metrics(records)
        self.assertEqual(result['settled_games'],1)
        self.assertEqual(result['excluded'],{'not_original':3,'invalid_pregame_timestamp':5})

    def test_duplicate_originals_exclude_every_copy_even_when_identical(self):
        for conflicting in (False,True):
            with self.subTest(conflicting=conflicting):
                first=original(2)
                other=deepcopy(first)
                if conflicting:
                    other['date']='2026-09-02'
                    other['evaluation']['winner_brier']=0.
                result=worker.prospective_metrics([original(),first,other])
                self.assertEqual(result['settled_games'],1)
                self.assertEqual(result['excluded']['duplicate_original'],2)
                self.assertEqual(result['winner_brier'],.16)

    def test_duplicated_games_cannot_reach_sample_threshold(self):
        records=[original(i,i%10) for i in range(15)]
        result=worker.prospective_metrics(records+deepcopy(records))
        self.assertEqual(result['settled_games'],0)
        self.assertEqual(result['excluded']['duplicate_original'],30)
        self.assert_no_interval(result)

    def test_malformed_identity_final_and_evaluation_do_not_enter_sample(self):
        records=[original(),None,[],{**original(2),'game_id':None},
                 {**original(3),'date':'unknown'},{**original(4),'home':'LAN'}]
        for idx,final in enumerate(({'home':2,'away':2},{'home':3.5,'away':2},
                                    {'home':3,'away':-1},{}),start=5):
            records.append({**original(idx),'official_final':final})
        for idx,value in enumerate((float('nan'),float('inf'),-.01,1.01,None,'0.16',True,10**1000),start=9):
            record=original(idx)
            record['evaluation']['winner_brier']=value
            records.append(record)
        broken=original(20);broken['evaluation']={'correct_winner':True}
        records.append(broken)
        result=worker.prospective_metrics(records)
        self.assertEqual(result['settled_games'],1)
        self.assertEqual(result['excluded'],{'malformed_record':2,'invalid_identity':3,
                                           'malformed_final':4,'malformed_evaluation':9})
        json.dumps(result,allow_nan=False)

    def test_pending_original_has_no_settled_metrics(self):
        pending=original();pending.pop('evaluation');pending.pop('official_final')
        result=worker.prospective_metrics([pending])
        self.assertEqual(result['settled_games'],0)
        self.assertEqual(result['settled_dates'],0)
        self.assert_no_interval(result)

    def test_site_ignores_misnamed_original_copies_before_other_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'cloud_records'
            (state/'predictions').mkdir(parents=True)
            (root/'site').mkdir();(root/'site/index.html').write_text('<html/>')
            record=original()
            frozen=json.dumps(record)
            (state/'predictions/1.json').write_text(frozen)
            (state/'predictions/1_copy.json').write_text(frozen)
            with patch.object(worker,'STATE',state), \
                    patch.object(worker,'prospective_health_report',return_value={}), \
                    patch.object(worker,'prospective_capture_report',return_value={}):
                worker.render_site(root,datetime(2026,9,3,tzinfo=UTC),{})
            data=json.loads((root/'site/data.json').read_text())
            self.assertEqual(data['prospective_performance']['settled_games'],1)
            self.assertEqual(data['full_distribution_validation']['unique_originals'],1)
            self.assertEqual(len(data['predictions']),1)
            self.assertEqual((state/'predictions/1.json').read_text(),frozen)


if __name__=='__main__':
    unittest.main()
