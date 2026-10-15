"""V19 independent backup scheduling, missed-game alerts and pregame integrity."""
import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cloud.v19_forecast_guard import evaluate,original_status
from cloud import preflight

UTC=timezone.utc
NOW=datetime(2026,10,15,1,10,tzinfo=UTC) # October 14, 9:10 PM ET

def game(start,state='Pre-Game',gid=849811):
    return {'gamePk':gid,'gameType':'L','officialDate':'2026-10-14',
      'gameDate':start.isoformat(),'status':{'detailedState':state,'abstractGameState':'Preview'},
      'teams':{'away':{'team':{'id':158}},'home':{'team':{'id':119}}}}

def feed(g,duplicate=False):
    def fetch(day):
        if day.isoformat()=='2026-10-14' or duplicate:
            return {'dates':[{'date':'2026-10-14','games':[g]}]}
        return {'dates':[]}
    return fetch

def record(root,gid,start,created,*,kind='original_pregame'):
    p=Path(root)/'cloud_records'/'predictions'/f'{gid}.json'
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'game_id':str(gid),'date':'2026-10-14',
       'home':'LAN','away':'MIL','game_start_utc':start.isoformat(),
       'forecast_created_utc':created.isoformat(),'forecast_kind':kind}))
    return p

class GuardTests(unittest.TestCase):
    def test_backup_dispatch_before_game_without_original_even_with_existing_early_preview(self):
        start=NOW+timedelta(minutes=23)
        g=game(start)
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/'cloud_records/preliminary/849811.json'
            q.parent.mkdir(parents=True)
            q.write_text('{}')
            out=evaluate(d,NOW,feed(g,duplicate=True))
        self.assertEqual(out['eligible_games'],1)
        self.assertEqual(out['dispatch_game_ids'],['849811'])
        self.assertEqual(out['status'],'needs_backup_dispatch')
        self.assertEqual(out['missed_game_ids'],[])

    def test_dispatch_hours_early_to_cover_cron_delay(self):
        with tempfile.TemporaryDirectory() as d:
            out=evaluate(d,NOW,feed(game(NOW+timedelta(hours=3))))
        self.assertEqual(out['dispatch_game_ids'], ['849811'])

    def test_existing_valid_original_means_no_dispatch_or_false_incident(self):
        start=NOW+timedelta(minutes=25)
        with tempfile.TemporaryDirectory() as d:
            record(d,849811,start,NOW-timedelta(minutes=5))
            out=evaluate(d,NOW,feed(game(start)))
        self.assertEqual(out['already_recorded_game_ids'],['849811'])
        self.assertEqual(out['dispatch_game_ids'],[])

    def test_after_mlb_actual_first_pitch_reports_missing_and_never_dispatches(self):
        start=NOW-timedelta(minutes=20)
        with tempfile.TemporaryDirectory() as d:
            result=evaluate(d,NOW,feed(game(start,state='In Progress')))
        self.assertEqual(result['missed_game_ids'],['849811'])
        self.assertEqual(result['dispatch_game_ids'],[])
        self.assertEqual(result['status'],'missing_original_after_official_start')

    def test_warmups_after_scheduled_start_is_not_said_to_have_started(self):
        start=NOW-timedelta(minutes=7)
        with tempfile.TemporaryDirectory() as d:
            out=evaluate(d,NOW,feed(game(start,state='Warmup')))
        self.assertEqual(out['missed_game_ids'],[])
        self.assertEqual(out['dispatch_game_ids'],[])

    def test_last_minutes_risk_without_fabricated_dispatch(self):
        start=NOW+timedelta(minutes=6)
        with tempfile.TemporaryDirectory() as d:
            out=evaluate(d,NOW,feed(game(start)))
        self.assertEqual(out['at_risk_game_ids'],['849811'])
        self.assertEqual(out['dispatch_game_ids'],[])

    def test_invalid_original_cannot_hide_missed_first_pitch(self):
        start=NOW-timedelta(minutes=15)
        with tempfile.TemporaryDirectory() as d:
            record(d,849811,start,NOW+timedelta(minutes=3))
            out=evaluate(d,NOW,feed(game(start,'Final')))
        self.assertEqual(out['invalid_original_game_ids'],['849811'])
        self.assertEqual(out['missed_game_ids'],['849811'])

    def test_older_than_tracking_launch_and_expired_coverage_not_reported(self):
        early=game(NOW-timedelta(days=1,minutes=30),state='Final')
        early['officialDate']='2026-10-13'
        with tempfile.TemporaryDirectory() as d:
            result=evaluate(d,NOW,lambda day:{'dates':[{'date':'2026-10-13','games':[early]}]})
        self.assertEqual(result['missed_game_ids'],[])
        g=game(NOW-timedelta(hours=20),state='Final')
        with tempfile.TemporaryDirectory() as d:
            out=evaluate(d,NOW,feed(g))
        self.assertEqual(out['missed_game_ids'],[])

    def test_out_of_window_or_postponed_does_not_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            for lead,state in ((245,'Pre-Game'),(8,'Pre-Game'),(23,'Postponed'),(23,'In Progress')):
                with self.subTest(lead=lead,state=state):
                    out=evaluate(d,NOW,feed(game(NOW+timedelta(minutes=lead),state=state)))
                    self.assertEqual(out['dispatch_game_ids'],[])

    def test_no_silent_green_on_total_official_schedule_outage(self):
        with tempfile.TemporaryDirectory() as d:
            def fails(day):
                raise OSError('MLB source offline')
            with self.assertRaises(OSError):
                evaluate(d,NOW,fetcher=fails)

    def test_reject_untrusted_forecast_timestamp_and_wrong_game_id(self):
        start=NOW+timedelta(minutes=25)
        g=game(start)
        with tempfile.TemporaryDirectory() as d:
            path=record(d,849811,start,NOW-timedelta(minutes=1))
            invalid=json.loads(path.read_text())
            invalid['game_id']='849999'
            path.write_text(json.dumps(invalid))
            self.assertEqual(original_status(d,'849811',g),'invalid')

if __name__=='__main__':unittest.main()
