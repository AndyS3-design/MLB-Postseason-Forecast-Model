"""Offline checks for official-only, pregame pitcher-history enrichment."""
from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from cloud.starter_backfill import backfill_match_starters, _prior_finals
from ingest_mlb import COLUMNS
from v4_sources import pitcher_snapshot


def final_row(day, game_id):
    row = {k: '' for k in COLUMNS}
    row.update(date=day, year='2026', home='MIL', away='LAN', game_id=str(game_id),
               home_final='2', away_final='1', game_type='R')
    return row


def fake_details(game, target_home, target_away):
    gid = str(game['game_id'])
    target = gid
    h_id = 'MLB-200' if target in target_home else 'MLB-900'
    a_id = 'MLB-100' if target in target_away else 'MLB-800'
    rows = []
    for side, pid in (('home', h_id), ('away', a_id)):
        rows.append(dict(date=game['date'], home='MIL', away='LAN', side=side,
                         game_num='',game_id=gid,pitcher_id=pid,sp_hand='R',
                         sp_outs='18',sp_er='1',sp_k='8',sp_bb='2',sp_hr='0',
                         bp_outs='9',bp_er='1',pitchers_used='3'))
    people = [dict(pitcher_id=r['pitcher_id'],name=r['pitcher_id'],hand='R',
                   season=2026,team=game[r['side']]) for r in rows]
    return rows,people


class StarterBackfillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.rows = [final_row(f'2026-10-{n:02}', 800000+n) for n in range(1,10)]
        # Same-day 'completed' result must be excluded even if mistakenly
        # already present in source files before predicting another game.
        self.rows.append(final_row('2026-10-13', 800020))
        with (self.dir/'mlb_2026_regular.csv').open('w',newline='') as f:
            wr=csv.DictWriter(f,fieldnames=COLUMNS)
            wr.writeheader();wr.writerows(self.rows)
        self.match = dict(id='900000',date='2026-10-13',home='MIL',away='LAN',
                          home_pitcher_id='MLB-200',away_pitcher_id='MLB-100')
        self.home_games={'800001','800003','800005','800007'}
        self.away_games={'800002','800004','800006','800008'}
        self.seen=[]

    def get_log(self,url):
        pid='100' if '/100/' in url else '200'
        ids=self.away_games if pid=='100' else self.home_games
        return {'stats':[{'splits':[{'game':{'gamePk':int(gid)}} for gid in ids]
                                  +[{'game':{'gamePk':800020}}]}]}

    def get_boxscore(self,game,cache):
        self.seen.append(game['game_id'])
        return fake_details(game,self.home_games,self.away_games)

    def test_targeted_backfill_fixes_both_starters(self):
        r=backfill_match_starters(self.dir,self.match,'2026-10-13',
                                 fetcher=self.get_log,boxscore_loader=self.get_boxscore)
        self.assertEqual(r['status'],'complete')
        self.assertGreaterEqual(r['sides']['home']['prior_verified_starts_after'],3)
        self.assertGreaterEqual(r['sides']['away']['prior_verified_starts_after'],3)
        self.assertTrue(r['new_boxscores']>=6)
        self.assertNotIn('800020',self.seen)
        self.assertGreaterEqual(pitcher_snapshot(self.dir,'MLB-200','2026-10-13')['known'],3)
        self.assertGreaterEqual(pitcher_snapshot(self.dir,'MLB-100','2026-10-13')['known'],3)

    def test_no_new_fetches_on_repeat(self):
        backfill_match_starters(self.dir,self.match,'2026-10-13',
                               fetcher=self.get_log,boxscore_loader=self.get_boxscore)
        first=self.seen.copy();self.seen=[]
        next_run=backfill_match_starters(self.dir,self.match,'2026-10-13',
                                        fetcher=self.get_log,boxscore_loader=self.get_boxscore)
        self.assertEqual(self.seen,[])
        self.assertEqual(next_run['new_boxscores'],0)
        self.assertTrue(first)

    def test_log_unavailable_falls_back_to_verified_final_team_games(self):
        def missing(_):raise TimeoutError('MLB API not reachable')
        r=backfill_match_starters(self.dir,self.match,'2026-10-13',
                                 fetcher=missing,boxscore_loader=self.get_boxscore)
        self.assertEqual(r['status'],'complete')
        self.assertTrue(r['errors'])
        self.assertNotIn('800020',self.seen)

    def test_missing_id_remains_unknown(self):
        self.match['away_pitcher_id']=''
        r=backfill_match_starters(self.dir,self.match,'2026-10-13',
                                 fetcher=self.get_log,boxscore_loader=self.get_boxscore)
        self.assertEqual(r['status'],'partial')
        self.assertEqual(r['sides']['away']['prior_verified_starts_after'],0)
        self.assertIn('not announced',r['sides']['away']['status'])

    def test_refuses_wrong_boxscore_identity(self):
        def bad(game,cache):
            rows,people=self.get_boxscore(game,cache)
            rows[0]['game_id']='something-else'
            return rows,people
        r=backfill_match_starters(self.dir,self.match,'2026-10-13',
                                 fetcher=self.get_log,boxscore_loader=bad)
        self.assertEqual(r['status'],'partial')
        self.assertEqual(r['new_boxscores'],0)
        self.assertTrue(r['errors'])
        self.assertFalse((self.dir/'advanced_pitching_details.csv').exists())

    def test_existing_files_are_not_modified_for_future_game(self):
        self.assertNotIn('800020',_prior_finals(self.dir,date(2026,10,13)))
        self.assertIn('800009',_prior_finals(self.dir,date(2026,10,13)))

if __name__=='__main__':unittest.main()

class WorkerIntegrationTests(unittest.TestCase):
    def test_backfill_runs_before_model_assets(self):
        from unittest.mock import patch
        from datetime import datetime, timezone, timedelta
        from cloud import worker
        now = datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc)
        game = {'id':'900002','date':'2026-10-13','home':'MIL','away':'LAN',
                'home_pitcher_id':'MLB-200','away_pitcher_id':'MLB-100',
                'game_type':'L','status':'Scheduled',
                'start_utc':(now+timedelta(minutes=20)).isoformat()}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'data').mkdir()
            old_state=worker.STATE
            worker.STATE=root/'cloud_records'
            call_order=[]
            def fake_backfill(*args,**kwargs):
                call_order.append('backfill')
                return {'status':'complete'}
            def fake_assets(*args,**kwargs):
                call_order.append('assets')
                return {'test':True}
            def fake_store(*args,**kwargs):
                call_order.append('forecast')
                self.assertEqual(kwargs['starter_backfill']['status'],'complete')
                return {'status':'saved'}
            try:
                with patch.object(worker,'fetch_schedule',return_value=[game]),\
                     patch.object(worker,'backfill_match_starters',side_effect=fake_backfill),\
                     patch.object(worker,'new_games',return_value=[]),\
                     patch.object(worker,'build_assets',side_effect=fake_assets),\
                     patch.object(worker,'store_pregame',side_effect=fake_store),\
                     patch.object(worker,'settle',return_value=0),\
                     patch.object(worker,'render_site',return_value=0),\
                     patch.object(worker,'utcnow',return_value=now):
                    worker.run(root=root, now=now,network=True,fast=True)
                self.assertEqual(call_order,['backfill','assets','forecast'])
            finally:
                worker.STATE=old_state
