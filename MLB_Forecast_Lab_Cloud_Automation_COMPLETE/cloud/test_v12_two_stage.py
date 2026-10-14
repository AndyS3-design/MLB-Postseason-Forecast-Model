"""V12 two-stage forecast contract: genuine early + genuinely fresh final."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cloud import worker
from cloud.preflight import find_preliminary_games, should_run
from cloud.two_stage import eligible_preliminary, paired_stage_metrics
from cloud.v9_tracking import load_originals
from cloud.v8_evaluate import from_files

UTC = timezone.utc
DAY = "2026-10-14"
EARLY = datetime(2026, 10, 14, 14, 10, tzinfo=UTC)  # 10:10 AM ET
START = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)  # 8 PM ET
FINAL = START - timedelta(minutes=20)


def match():
    return {
        'id':'20261014','date':DAY,'home':'MIL','away':'LAN',
        'home_name':'Milwaukee Brewers','away_name':'Los Angeles Dodgers',
        'game_type':'L','status':'Scheduled','start_utc':START.isoformat(),
        'home_pitcher':'Not announced','away_pitcher':'Not announced',
    }


def model_output(p=.6):
    return {
        'model_version':'v12-test',
        'forecast':{'v6_display_score':{'away':3,'home':4,'total':7,'probability':.04},
                    'home_win_probability':p,'home_expected_runs':4.,
                    'away_expected_runs':3.,'total_expected_runs':7.,
                    'under_6_5_probability':.45,'total_pmf':{'7':1.},
                    'score_grid':{'cells':[[.01]*11]*11}},
        'provenance':{'pitcher_coverage':{'home':0,'away':0},
                      'model_frozen_training':'2023-25'},
        'personnel':{'home':{'lineup':[]},'away':{'lineup':[]}},
        'adjustments':{'postseason_scoring':{'factor':1.},
                       'starter_total_rate':{'weight':0.},
                       'park':{'factor':1.},'weather':{'factor':1.}},
        'data_gaps':['pitcher details pending'], 'baseline':{'elo_home_win':.51},
    }


def raw_game(game_id='20261014', state='Scheduled'):
    return {'gamePk':int(game_id),'gameDate':START.isoformat(),
            'officialDate':DAY,'gameType':'L',
            'status':{'detailedState':state}}


class TwoStageTests(unittest.TestCase):
    def test_early_window_and_live_rejection(self):
        g=match()
        self.assertTrue(worker.can_preliminary(g,EARLY))
        self.assertFalse(worker.can_preliminary(g,EARLY-timedelta(minutes=11)))
        self.assertFalse(worker.can_preliminary({**g,'date':'2026-10-13'},EARLY))
        self.assertFalse(worker.can_preliminary({**g,'status':'In Progress'},EARLY))
        self.assertFalse(worker.can_preliminary(g,START-timedelta(minutes=30)))
        self.assertTrue(worker.can_forecast(g,FINAL))
        self.assertFalse(worker.can_forecast(g,EARLY))

    def test_gate_only_wakes_for_missing_preliminary_and_keeps_final_ids_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            payload=lambda day:{'dates':[{'date':DAY,'games':[raw_game()]}]}
            self.assertEqual(len(find_preliminary_games(EARLY,directory,payload)),1)
            decision=should_run(EARLY,root=directory,fetcher=payload)
            self.assertTrue(decision['run'])
            self.assertEqual(decision['reason'],'early preliminary preview')
            self.assertEqual(decision['approaching_games'],[])
            self.assertEqual(decision['preliminary_games'][0]['id'],'20261014')
            path=Path(directory)/'cloud_records/preliminary/20261014.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
            self.assertFalse(should_run(EARLY,root=directory,fetcher=payload)['run'])
            path.unlink()
            self.assertEqual(find_preliminary_games(EARLY-timedelta(minutes=11),directory,payload),[])
            self.assertEqual(find_preliminary_games(EARLY,directory,
                             lambda day:{'dates':[{'date':DAY,'games':[raw_game(state='In Progress')]}]}),[])

    def test_early_final_preserved_and_primary_metrics_exclude_early(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'site').mkdir()
            (root/'site/index.html').write_text('placeholder',encoding='utf-8')
            g=match()
            with patch.object(worker,'STATE',root/'cloud_records'),\
                 patch.object(worker,'game_evidence',return_value=None),\
                 patch.object(worker,'generate',side_effect=[model_output(.60),model_output(.53)]),\
                 patch.object(worker,'team_indices',return_value={'teams':{}}):
                args=(g,EARLY,[],root,{'enriched':[]})
                x=worker.store_pregame(*args,preliminary=True)
                self.assertEqual(x['status'],'preliminary_saved')
                prelim=root/'cloud_records/preliminary/20261014.json'
                old=prelim.read_bytes()
                self.assertEqual(worker.store_pregame(*args,preliminary=True)['status'],
                                 'preliminary_already_frozen')
                self.assertEqual(prelim.read_bytes(),old)
                self.assertFalse((root/'cloud_records/predictions/20261014.json').exists())
                # Final is computed again from the later timestamp, not cloned from preview.
                y=worker.store_pregame(g,FINAL,[],root,{'enriched':[]})
                self.assertEqual(y['status'],'saved')
                frozen=root/'cloud_records/predictions/20261014.json'
                self.assertEqual(json.loads(frozen.read_text())['predicted_home_win'],.53)
                self.assertEqual(json.loads(prelim.read_text())['predicted_home_win'],.60)
                self.assertEqual(prelim.read_bytes(),old)
                self.assertEqual(worker.store_pregame(g,FINAL,[],root,{'enriched':[]})['status'],
                                 'already_frozen')
                self.assertEqual(len(load_originals(root)[0]),1)
                self.assertEqual(from_files(root)['coverage']['original_forecasts'],1)
                worker.render_site(root,FINAL,{'status':'test'})
                published=json.loads((root/'site/data.json').read_text())
                self.assertEqual(len(published['predictions']),2)
                self.assertEqual([r['forecast_kind'] for r in published['predictions']],
                                 ['original_pregame','preliminary_pregame'])
                self.assertAlmostEqual(published['predictions'][0]
                                       ['preliminary_comparison']['predicted_home_win'],.60)
                self.assertEqual(published['two_stage_comparison']['paired_settled_games'],0)

                # Official settling augments FINAL only; provisional JSON stays unchanged.
                original=json.loads(frozen.read_text())
                original['official_final']={'home':4,'away':2}
                worker.encode_json(frozen,original)
                result=paired_stage_metrics(root)
                self.assertEqual(result['paired_settled_games'],1)
                self.assertAlmostEqual(result['preliminary_winner_brier'],(.60-1)**2)
                self.assertAlmostEqual(result['final_winner_brier'],(.53-1)**2)
                self.assertEqual(prelim.read_bytes(),old)

    def test_early_without_final_remains_visible_but_not_official(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'site').mkdir()
            (root/'site/index.html').write_text('placeholder')
            with patch.object(worker,'STATE',root/'cloud_records'),\
                 patch.object(worker,'game_evidence',return_value=None),\
                 patch.object(worker,'generate',return_value=model_output()),\
                 patch.object(worker,'team_indices',return_value={'teams':{}}):
                worker.store_pregame(match(),EARLY,[],root,{'enriched':[]},preliminary=True)
                worker.render_site(root,START+timedelta(hours=1),{'status':'test'})
                view=json.loads((root/'site/data.json').read_text())
                self.assertEqual([p['forecast_kind'] for p in view['predictions']],
                                 ['preliminary_pregame'])
                self.assertEqual(view['model_health']['coverage']['original_forecasts'],0)
                self.assertEqual(view['two_stage_comparison']['preliminary_without_final_count'],1)

    def test_early_lookup_failure_cannot_suppress_final_game_window(self):
        with tempfile.TemporaryDirectory() as directory:
            counter=[0]
            def sometimes_fails(day):
                counter[0]+=1
                if counter[0]==3:
                    raise OSError('independent early schedule unavailable')
                return {'dates':[{'date':DAY,'games':[raw_game()]}]}
            decision=should_run(FINAL,root=directory,fetcher=sometimes_fails)
            self.assertTrue(decision['run'])
            self.assertEqual(decision['reason'],'pregame window')
            self.assertEqual(decision['approaching_games'][0]['id'],'20261014')

    def test_changed_game_status_or_timing_does_not_create_early(self):
        g=match()
        self.assertFalse(eligible_preliminary(g['id'],DAY,START.isoformat(),'L',
                                               'Suspended',EARLY))
        self.assertFalse(eligible_preliminary(g['id'],DAY,START.isoformat(),'L',
                                               'Scheduled',START+timedelta(seconds=1)))
        self.assertFalse(eligible_preliminary(g['id'],DAY,START.isoformat(),'L',
                                               'Scheduled',datetime(2026,10,14,14,0)))


if __name__ == '__main__':
    unittest.main()
