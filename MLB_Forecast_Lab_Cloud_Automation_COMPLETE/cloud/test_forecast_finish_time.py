"""Verify a model calculation cannot be backdated if it finishes after first pitch."""
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from cloud import worker

def fixture(now,lead_minutes=20):
    return dict(id='745111',date=now.date().isoformat(),home='MIL',away='LAN',
        home_name='Milwaukee Brewers',away_name='Los Angeles Dodgers',
        start_utc=(now+timedelta(minutes=lead_minutes)).isoformat(),
        status='Scheduled',game_type='L')

def fake_generate(*args,**kwargs):
    f={'v6_display_score':{'away':2,'home':3,'total':5,'probability':.02},
       'home_win_probability':.55,'home_expected_runs':3.2,'away_expected_runs':3.1,
       'total_expected_runs':6.3,'under_6_5_probability':.55,'total_pmf':{'5':.5,'7':.5},
       'score_grid':{'cells':[[.005]*11]*11}}
    return {'forecast':f,'model_version':'v8-test',
       'provenance':{'pitcher_coverage':{'home':5,'away':5},
           'model_frozen_training':'2016–2025'},
       'personnel':{'home':{'lineup':[],'bullpen':{}},'away':{'lineup':[],'bullpen':{}}},
       'adjustments':{'postseason_scoring':{'factor':.9},
         'starter_total_rate':{'weight':.25},'park':{'factor':1},'weather':{'factor':1}},
       'data_gaps':[],'baseline':{'elo_home_win':.53}}

class CompletionTimestampTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,13,18,0,tzinfo=timezone.utc)

    def attempt(self,directory,minutes,lead=20):
        original_state=worker.STATE
        worker.STATE=Path(directory)/'cloud_records'
        (worker.STATE/'predictions').mkdir(parents=True)
        try:
            with patch.object(worker,'game_evidence',return_value=None),\
                 patch.object(worker,'generate',side_effect=fake_generate),\
                 patch.object(worker,'team_indices',return_value={'teams':{}}),\
                 patch.object(worker,'monotonic',side_effect=(100.,100.+minutes*60,100.+minutes*60+5)):
                 return worker.store_pregame(
                     fixture(self.now,lead),self.now,[],Path(directory),{'enriched':[]})
        finally:
            worker.STATE=original_state

    def test_rejects_model_finishing_after_first_pitch(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,'crossed first pitch'):
                self.attempt(tmp,21)
            self.assertFalse((Path(tmp)/'cloud_records/predictions/745111.json').exists())

    def test_rejects_post_formatting_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_state=worker.STATE
            worker.STATE=Path(tmp)/'cloud_records'
            (worker.STATE/'predictions').mkdir(parents=True)
            try:
                with patch.object(worker,'game_evidence',return_value=None),\
                    patch.object(worker,'generate',side_effect=fake_generate),\
                    patch.object(worker,'team_indices',return_value={'teams':{}}),\
                    patch.object(worker,'monotonic',side_effect=(100.,100.+19*60,100.+21*60)):
                    with self.assertRaisesRegex(RuntimeError,'persisted after first pitch'):
                        worker.store_pregame(fixture(self.now),self.now,[],Path(tmp),{'enriched':[]})
                self.assertFalse((worker.STATE/'predictions/745111.json').exists())
            finally:
                worker.STATE=original_state

    def test_records_end_time_not_start_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=self.attempt(tmp,1)
            self.assertEqual(result['status'],'saved')
            record=json.loads((Path(tmp)/'cloud_records/predictions/745111.json').read_text())
            completion=datetime.fromisoformat(record['forecast_created_utc'])
            self.assertGreater(completion,self.now)
            self.assertLess(completion,self.now+timedelta(minutes=20))
            self.assertAlmostEqual(record['minutes_before_game'],18.9,places=1)

if __name__=='__main__':unittest.main()
