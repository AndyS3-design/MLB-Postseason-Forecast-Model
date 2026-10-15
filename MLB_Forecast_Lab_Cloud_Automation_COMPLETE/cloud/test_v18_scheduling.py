"""Official-date scheduling and bounded retries for immutable pregame stages."""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cloud import preflight, worker
from cloud.test_v12_two_stage import EARLY, match, model_output
from cloud.test_v15_lineup_refresh import lineup_snapshot

UTC=timezone.utc


def official_game(game):
    return {'gamePk':int(game['id']),'officialDate':game['date'],
            'gameDate':game['start_utc'],'gameType':game['game_type'],
            'status':{'detailedState':game['status']},
            'teams':{'home':{'team':{'id':158}},'away':{'team':{'id':119}}}}


def schedule(game):
    def fetch(day):
        return {'dates':[{'date':game['date'],'games':[official_game(game)]}]} if day.isoformat()==game['date'] else {'dates':[]}
    return fetch


def save(root,directory,name,value):
    path=Path(root)/'cloud_records'/directory/(name+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value),encoding='utf-8')
    return path


def frozen_preview(game,now):
    return {'game_id':game['id'],'date':game['date'],'home':game['home'],
            'away':game['away'],'model_version':'older-model',
            'game_start_utc':game['start_utc'],
            'forecast_created_utc':(now-timedelta(hours=1)).isoformat()}


def request(game,kind):
    return {'game_id':game['id'],'date':game['date'],'kind':kind,
            'required_model_version':preflight.VERSION}


class OfficialDateTests(unittest.TestCase):
    def test_evening_final_after_utc_midnight_uses_official_date(self):
        now=datetime(2026,7,15,1,45,tzinfo=UTC)
        game={**match(),'date':'2026-07-14','game_type':'R',
              'start_utc':'2026-07-15T02:10:00+00:00'}
        queried=[]
        fetch=schedule(game)
        def tracked(day):
            queried.append(day)
            return fetch(day)
        with tempfile.TemporaryDirectory() as root:
            save(root,'preliminary',game['id'],frozen_preview(game,now))
            result=preflight.should_run(now,root=root,fetcher=tracked)
        self.assertTrue(result['run'])
        self.assertEqual(result['reason'],'pregame window')
        self.assertEqual([g['id'] for g in result['approaching_games']],[game['id']])
        self.assertEqual(set(queried),{date(2026,7,13),date(2026,7,14),date(2026,7,15)})
        self.assertEqual(len(queried),3)  # All gate stages share each day's lookup.

    def test_adjacent_official_day_and_dst_use_real_utc_first_pitch(self):
        cases=(
            (datetime(2026,3,8,4,45,tzinfo=UTC),'2026-03-07'),
            (datetime(2026,11,1,5,45,tzinfo=UTC),'2026-10-31'),
            (datetime(2026,11,1,6,45,tzinfo=UTC),'2026-10-31'),
        )
        for now,official_day in cases:
            with self.subTest(now=now):
                game={**match(),'date':official_day,'game_type':'R',
                      'start_utc':(now+timedelta(minutes=25)).isoformat()}
                games=preflight.find_approaching_games(now,schedule(game))
                self.assertEqual(len(games),1)
                self.assertEqual(games[0]['lead_minutes'],25)

    def test_partial_schedule_outage_keeps_verified_match(self):
        now=datetime(2026,7,15,1,45,tzinfo=UTC)
        game={**match(),'date':'2026-07-14',
              'start_utc':(now+timedelta(minutes=25)).isoformat()}
        def fetch(day):
            if day.isoformat()==game['date']:return schedule(game)(day)
            raise TimeoutError('adjacent date unavailable')
        self.assertEqual(len(preflight.find_approaching_games(now,fetch)),1)

    def test_fast_worker_fetches_previous_official_day_after_eastern_midnight(self):
        now=datetime(2026,7,15,4,10,tzinfo=UTC)
        game={**match(),'date':'2026-07-14','game_type':'R',
              'start_utc':(now+timedelta(minutes=20)).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(worker,'STATE',root/'cloud_records'),\
                 patch.object(worker,'fetch_schedule',side_effect=lambda day:[game] if day.isoformat()==game['date'] else []) as fetch,\
                 patch.object(worker,'backfill_match_starters',return_value={'status':'complete'}),\
                 patch.object(worker,'new_games',return_value=[]),\
                 patch.object(worker,'build_assets',return_value={}),\
                 patch.object(worker,'store_pregame',return_value={'status':'saved'}) as store,\
                 patch.object(worker,'settle',return_value=0),\
                 patch.object(worker,'render_site',return_value=0),\
                 patch.object(worker,'utcnow',return_value=now):
                worker.run(root=root,now=now,network=True,fast=True)
            self.assertEqual({call.args[0] for call in fetch.call_args_list},
                             set(preflight.official_schedule_days(now)))
            store.assert_called_once()
            self.assertEqual(store.call_args.args[0]['id'],game['id'])

    def test_gate_direct_script_needs_no_model_dependencies(self):
        proc=subprocess.run([sys.executable,'-S','cloud/preflight.py','--help'],
                            cwd=preflight.APP_ROOT,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stderr)


class PendingRequestTests(unittest.TestCase):
    def setUp(self):
        self.now=EARLY
        self.game={**match(),'start_utc':(self.now+timedelta(hours=2)).isoformat()}
        self.kinds=(
            ('lineup_refresh_requests','one_time_confirmed_lineup_refresh','lineup_previews'),
            ('preliminary_update_requests','one_time_preliminary_update','preliminary_revisions'),
            ('revision_requests','one_time_pregame_revision','revisions'),
        )

    def prepare(self,root,directory,kind):
        record_directory='predictions' if directory=='revision_requests' else 'preliminary'
        original=save(root,record_directory,self.game['id'],frozen_preview(self.game,self.now))
        authorization=save(root,directory,self.game['id'],request(self.game,kind))
        return original,authorization

    def decision(self,root,game=None,now=None):
        return preflight.should_run(now or self.now,root=root,
                                    fetcher=schedule(game or self.game))

    def test_pending_requests_wake_without_new_preliminary_or_final(self):
        for directory,kind,_ in self.kinds:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as root:
                original,_=self.prepare(root,directory,kind)
                before=original.read_bytes()
                result=self.decision(root)
                self.assertTrue(result['run'])
                self.assertEqual(result['reason'],'authorized pregame request')
                self.assertEqual(result['preliminary_games'],[])
                self.assertEqual(result['approaching_games'],[])
                self.assertEqual(result['pending_request_games'][0]['request_kind'],kind)
                self.assertEqual(original.read_bytes(),before)

    def test_preliminary_retry_earliest_hour_follows_dst(self):
        for now in (datetime(2026,3,8,13,59,tzinfo=UTC),
                    datetime(2026,11,1,14,59,tzinfo=UTC)):
            game={**self.game,'date':now.date().isoformat(),
                  'start_utc':(now+timedelta(hours=2)).isoformat()}
            with self.subTest(now=now),tempfile.TemporaryDirectory() as root:
                save(root,'preliminary',game['id'],frozen_preview(game,now))
                save(root,'lineup_refresh_requests',game['id'],request(game,self.kinds[0][1]))
                self.assertFalse(self.decision(root,game,now)['run'])
                self.assertTrue(self.decision(root,game,now+timedelta(minutes=1))['run'])

    def test_waiting_for_official_lineups_retries_until_refresh_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            g=self.game
            early,_=self.prepare(root,'lineup_refresh_requests',self.kinds[0][1])
            before=early.read_bytes()
            confirmed=model_output(.54)
            confirmed['model_version']=worker.VERSION
            for side in ('home','away'):
                confirmed['personnel'][side]['lineup']=lineup_snapshot()['confirmed_lineups'][side]
            with patch.object(worker,'STATE',root/'cloud_records'),\
                 patch.object(worker,'game_evidence',side_effect=[lineup_snapshot(False),lineup_snapshot()]),\
                 patch.object(worker,'generate',return_value=confirmed),\
                 patch.object(worker,'team_indices',return_value={'teams':{}}):
                self.assertTrue(self.decision(root)['run'])
                waiting=worker.store_pregame(g,self.now,[],root,{'enriched':[]},lineup_update=True)
                self.assertEqual(waiting['status'],'lineup_refresh_waiting_for_both_official_orders')
                retry=self.now+timedelta(minutes=5)
                self.assertTrue(self.decision(root,now=retry)['run'])
                complete=worker.store_pregame(g,retry,[],root,{'enriched':[]},lineup_update=True)
                self.assertEqual(complete['status'],'lineup_confirmed_saved')
                self.assertFalse(self.decision(root,now=retry+timedelta(minutes=5))['run'])
                self.assertEqual(early.read_bytes(),before)

    def test_fulfilled_malformed_and_wrong_identity_requests_stay_asleep(self):
        for directory,kind,target in self.kinds:
            for invalid in ('fulfilled','invalid_json','not_object','wrong_id','wrong_date','wrong_kind','wrong_team','wrong_record_id'):
                with self.subTest(kind=kind,invalid=invalid),tempfile.TemporaryDirectory() as root:
                    original,authorization=self.prepare(root,directory,kind)
                    if invalid=='fulfilled':save(root,target,self.game['id']+'_saved',{})
                    elif invalid=='invalid_json':authorization.write_text('{')
                    elif invalid=='not_object':authorization.write_text('[]')
                    elif invalid.startswith('wrong_record') or invalid=='wrong_team':
                        data=json.loads(original.read_text())
                        data['home' if invalid=='wrong_team' else 'game_id']='incorrect'
                        original.write_text(json.dumps(data))
                    else:
                        data=json.loads(authorization.read_text())
                        field={'wrong_id':'game_id','wrong_date':'date','wrong_kind':'kind'}[invalid]
                        data[field]='incorrect'
                        authorization.write_text(json.dumps(data))
                    self.assertFalse(self.decision(root)['run'])

    def test_expired_or_live_requests_never_wake_retry(self):
        for directory,kind,_ in self.kinds:
            cases=[('live',{**self.game,'status':'In Progress'},self.now),
                   ('wrong_type',{**self.game,'game_type':'S'},self.now)]
            if directory=='revision_requests':
                cases.extend([('too_early',{**self.game,'start_utc':(self.now+timedelta(minutes=151)).isoformat()},self.now),
                              ('expired',self.game,self.now+timedelta(hours=2))])
            else:
                cases.extend([('expired',self.game,self.now+timedelta(minutes=76)),
                              ('prior_official_day',{**self.game,'date':'2026-10-13'},self.now)])
            for label,game,now in cases:
                with self.subTest(kind=kind,case=label),tempfile.TemporaryDirectory() as root:
                    self.prepare(root,directory,kind)
                    self.assertFalse(self.decision(root,game,now)['run'])

    def test_model_version_gate_and_existing_final_block_preview_updates(self):
        for directory,kind,_ in self.kinds[:2]:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as root:
                self.prepare(root,directory,kind)
                save(root,'predictions',self.game['id'],{})
                self.assertFalse(self.decision(root)['run'])
        for already_current in (False,True):
            with self.subTest(already_current=already_current),tempfile.TemporaryDirectory() as root:
                original,authorization=self.prepare(root,'preliminary_update_requests',self.kinds[1][1])
                path=original if already_current else authorization
                data=json.loads(path.read_text())
                data['model_version' if already_current else 'required_model_version']=preflight.VERSION if already_current else 'wrong-model'
                path.write_text(json.dumps(data))
                self.assertFalse(self.decision(root)['run'])


if __name__=='__main__':unittest.main()
