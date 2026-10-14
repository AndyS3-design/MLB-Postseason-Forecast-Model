"""Cross-session cloud safeguards; offline with small deterministic fixtures."""
import csv,datetime,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
from cloud.worker import (can_forecast,encode_json,read_json,prospective_metrics,
    settle,render_site,store_pregame,ROOT)
from cloud.refresh import save_merged,current_season_results,append_future_years
from ingest_mlb import COLUMNS

UTC=datetime.timezone.utc

def match(now,delta=20,game_id='77777'):
    return dict(id=game_id,date=now.date().isoformat(),home='MIL',away='LAN',
        home_name='Milwaukee Brewers',away_name='Los Angeles Dodgers',
        start_utc=(now+datetime.timedelta(minutes=delta)).isoformat(),
        game_type='L',status='Scheduled',away_pitcher_id='',home_pitcher_id='')

class CloudTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.datetime(2026,10,13,18,0,tzinfo=UTC)

    def test_accepts_true_pregame(self):
        self.assertTrue(can_forecast(match(self.now),self.now))

    def test_no_late_or_too_early_predictions(self):
        self.assertFalse(can_forecast(match(self.now,5),self.now))
        self.assertFalse(can_forecast(match(self.now,-5),self.now))
        self.assertFalse(can_forecast(match(self.now,95),self.now))

    def test_no_live_or_final(self):
        for status in ('In Progress','Final','Game Over','Delayed Start'):
            m=match(self.now);m['status']=status
            self.assertFalse(can_forecast(m,self.now))

    def test_timezones_use_utc_instants(self):
        now=datetime.datetime(2026,10,13,17,0,tzinfo=UTC)
        m=match(now)
        self.assertTrue(can_forecast(m,now.astimezone(ZoneInfo('America/New_York'))))

    def test_missing_game_id_cannot_be_frozen(self):
        m=match(self.now);m['id']=''
        self.assertFalse(can_forecast(m,self.now))

    def test_conflicting_game_ids_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'regular.csv';r=self.row()
            save_merged(p,[r]);q=r.copy();q['home']='CLE'
            with self.assertRaises(ValueError):save_merged(p,[q])
            with p.open() as f:self.assertEqual(list(csv.DictReader(f))[0]['home'],'MIL')

    def row(self):
        x={k:'' for k in COLUMNS}
        x.update(dict(game_id='77777',date='2026-10-12',year=2026,game_type='R',
                      home='MIL',away='LAN',home_final=2,away_final=3,source='test'))
        return x

    def test_repeat_game_id_updates_score_without_dupes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'regular.csv';r=self.row();save_merged(p,[r]);q=r.copy();q['home_final']=4
            self.assertEqual(save_merged(p,[q]),1)
            with p.open() as f:self.assertEqual(list(csv.DictReader(f))[0]['home_final'],'4')

    def test_api_strict_exclusive_cutoff(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            def fake(url):
                return {'dates':[{'date':'2026-10-13','games':[dict(
                  gamePk=77777,officialDate='2026-10-13',gameType='R',
                  gameDate='2026-10-13T19:00:00Z',status={'abstractGameState':'Final'},
                  teams={'away':{'team':{'id':119},'score':3},
                         'home':{'team':{'id':158},'score':2}})]}]}
            count=current_season_results(root,datetime.date(2026,10,13),fake)
            self.assertEqual(count,0)
            self.assertFalse((root/'data/mlb_2026_regular.csv').exists())

    def test_prediction_lock_and_replay_immutable(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'cloud_records/predictions').mkdir(parents=True)
            # Patch output file writes in a scratch directory and avoid running model.
            from cloud import worker
            old=worker.STATE
            worker.STATE=root/'cloud_records'
            try:
                now=self.now;m=match(now)
                fake_pred={'v6_display_score':{'away':3,'home':2,'total':5,'probability':.04},
                   'home_win_probability':.4,'home_expected_runs':3.2,'away_expected_runs':3.5,
                   'total_expected_runs':6.7,'under_6_5_probability':.48,
                   'total_pmf':{'5':.1,'6':.1,'7':.4,'8':.4},
                   'score_grid':{'cells':[[.01]*11]*11}}
                fake_res={'model_version':'testversion','forecast':fake_pred,
                   'provenance':{'pitcher_coverage':{'home':0,'away':0},
                                 'model_frozen_training':'2023-24'},
                   'personnel':{'home':{'lineup':[]},'away':{'lineup':[]}},
                   'adjustments':{'postseason_scoring':{'factor':.9},
                      'starter_total_rate':{'weight':0},'park':{'factor':1},'weather':{'factor':1}},
                   'data_gaps':['Starter unconfirmed'],
                   'baseline':{'elo_home_win':.51}}
                with patch.object(worker,'game_evidence',return_value=None),\
                     patch.object(worker,'generate',return_value=fake_res),\
                     patch.object(worker,'team_indices',return_value={'teams':{}}):
                    output=store_pregame(m,now,[],root,{'enriched':[]})
                    self.assertEqual(output['status'],'saved')
                    file=root/'cloud_records/predictions/77777.json'
                    before=file.read_bytes()
                    outcome=store_pregame(m,now,[],root,{'enriched':[]})
                    self.assertEqual(outcome['status'],'already_frozen')
                    self.assertEqual(file.read_bytes(),before)
                    self.assertEqual(read_json(file)['projected_score']['sum'],5)
            finally:worker.STATE=old

    def test_settlement_preserves_immutable_forecast(self):
        with tempfile.TemporaryDirectory() as t:
            from cloud import worker
            old=worker.STATE
            root=Path(t);worker.STATE=root/'cloud_records'
            try:
                p=root/'cloud_records/predictions/77777.json'
                item={'game_id':'77777','date':'2026-10-12','home':'MIL','away':'LAN',
                      'predicted_home_win':.4,'elo_home_win':.6,
                      'expected_runs':{'home':3.,'away':4.,'total':7.},
                      'under_6_5_probability':.45,'projected_score':{'home':3,'away':4}}
                encode_json(p,item)
                data=root/'data';data.mkdir()
                save_merged(data/'mlb_2026_regular.csv',[self.row()])
                self.assertEqual(settle(root),1)
                settled=read_json(p)
                self.assertEqual(settled['predicted_home_win'],.4)
                self.assertEqual(settled['official_final'],
                    {'home':2,'away':3,'settled_at_utc':settled['official_final']['settled_at_utc'],
                     'source':'Official MLB schedule API'})
                self.assertEqual(settle(root),0)
            finally:worker.STATE=old

    def test_prospective_metrics_tiny_sample_unreliable(self):
        records=[{'game_id':'77777','date':'2026-10-12','home':'MIL','away':'LAN',
                  'forecast_kind':'original_pregame',
                  'forecast_created_utc':'2026-10-12T22:40:00+00:00',
                  'game_start_utc':'2026-10-12T23:00:00+00:00',
                  'official_final':{'home':3,'away':2},
                  'evaluation':{'correct_winner':True,
                  'winner_brier':.16,'elo_brier':.21,'abs_run_error_per_team':1.,
                  'under_6_5_brier':.25}}]
        x=prospective_metrics(records)
        self.assertNotIn('elo_minus_model_brier_95_ci',x)
        self.assertEqual(x['settled_games'],1)

    def test_page_does_not_include_markets(self):
        html=(ROOT/'site/index.html').read_text().lower()
        for token in ('sportsbook','kalshi','prizepicks','underdog','odds api'):
            self.assertNotIn(token,html)

    def test_render_empty_forecasts_no_invented_scores(self):
        from cloud import worker
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'site').mkdir();(root/'cloud_records/predictions').mkdir(parents=True)
            (root/'site/index.html').write_text('placeholder')
            old=worker.STATE;worker.STATE=root/'cloud_records'
            try:
                self.assertEqual(render_site(root,self.now,{'status':'test'}),0)
                self.assertEqual(read_json(root/'site/data.json')['predictions'],[])
            finally:worker.STATE=old

if __name__=='__main__':unittest.main()

