"""V7 pregame timing, history bootstrap and recency training checks."""
from __future__ import annotations
import io,tempfile,unittest,zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cloud.preflight import find_approaching_games,should_run,MIN_LEAD_MINUTES,MAX_LEAD_MINUTES
from cloud.history_bootstrap import valid_archive,ensure_history
from cloud.worker import can_forecast

UTC=timezone.utc

def game(now,lead,state='Scheduled',kind='R'):
    return {'gamePk':5005,'gameDate':(now+timedelta(minutes=lead)).isoformat(),
            'gameType':kind,'status':{'detailedState':state}}

class GateTests(unittest.TestCase):
    def setUp(self):self.now=datetime(2026,10,13,19,35,tzinfo=UTC)
    def payload(self,rows):return {'dates':[{'games':rows}]}
    def test_gate_20_minutes(self):
        fetcher=lambda day:self.payload([game(self.now,20)]) if day==self.now.date() else self.payload([])
        self.assertTrue(should_run(self.now,fetcher=fetcher)['run'])
        self.assertEqual(len(find_approaching_games(self.now,fetcher)),1)
    def test_gate_early_and_after_start_are_skipped(self):
        for minutes in (120,9,-1):
            f=lambda day:self.payload([game(self.now,minutes)]) if day==self.now.date() else self.payload([])
            self.assertFalse(should_run(self.now,fetcher=f)['run'])
        f=lambda day:self.payload([game(self.now,10)]) if day==self.now.date() else self.payload([])
        self.assertTrue(should_run(self.now,fetcher=f)['run']) # valid late recovery wake
    def test_gate_rejects_live_or_final(self):
        for state in ('In Progress','Final','Suspended'):
            f=lambda day:self.payload([game(self.now,20,state)]) if day==self.now.date() else self.payload([])
            self.assertFalse(should_run(self.now,fetcher=f)['run'])
    def test_gate_fail_closed_and_manual(self):
        def failure(day):raise TimeoutError('no schedule')
        self.assertFalse(should_run(self.now,fetcher=failure)['run'])
        self.assertTrue(should_run(self.now,manual=True,fetcher=failure)['run'])
    def test_worker_predates_first_pitch(self):
        now=self.now
        def worker_game(lead):
            return {'id':'5005','date':now.date().isoformat(),'away':'LAN','home':'MIL',
                    'status':'Scheduled','game_type':'R',
                    'start_utc':(now+timedelta(minutes=lead)).isoformat()}
        for lead in (8,20,30):self.assertTrue(can_forecast(worker_game(lead),now))
        for lead in (-5,3,31,120):self.assertFalse(can_forecast(worker_game(lead),now))
    def test_gate_handles_next_utc_day(self):
        now=datetime(2026,10,13,23,45,tzinfo=UTC)
        f=lambda day:self.payload([game(now,20)]) if day==(now+timedelta(days=1)).date() else self.payload([])
        self.assertTrue(should_run(now,fetcher=f)['run'])

class BootstrapTests(unittest.TestCase):
    def test_rejects_corrupted_zip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gl2016.zip';p.write_text('broken')
            self.assertFalse(valid_archive(p,2016))
    def test_bootstrap_offline_fetched_zip(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            for y in range(2017,2023):
                (folder/f'GL{y}.TXT').write_bytes(b'fake-data'*70000)
            def fake_fetch(url,path):
                with zipfile.ZipFile(path,'w') as z:z.writestr('GL2016.TXT','x'*500)
            report=ensure_history(folder,fetcher=fake_fetch)
            self.assertEqual(report['downloaded'],[2016])
            self.assertEqual(report['unavailable'],{})
            self.assertTrue(valid_archive(folder/'gl2016.zip',2016))

if __name__=='__main__':unittest.main()
