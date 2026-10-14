import json,tempfile,unittest
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from cloud.v9_tracking import summarize,TRACKING_START

BASE=datetime(2026,10,15,0,tzinfo=timezone.utc)

def final(gameid,day='2026-10-14',home='MIL',away='LAN'):
    return dict(game_id=gameid,date=day,home=home,away=away,game_type='L',
                home_final='4',away_final='2')

def record(gameid,lead=20,day='2026-10-14'):
    start=datetime.fromisoformat(day+'T23:00:00+00:00')
    return dict(game_id=gameid,date=day,home='MIL',away='LAN',
        game_start_utc=start.isoformat(),forecast_created_utc=(start-timedelta(minutes=lead)).isoformat(),
        forecast_kind='original_pregame')

class TrackerTests(unittest.TestCase):
 def setup_files(self,root,records):
    path=Path(root)/'cloud_records/predictions'
    path.mkdir(parents=True)
    for obj in records:
        (path/(str(obj['game_id'])+'.json')).write_text(json.dumps(obj))
 def test_captured_missing_and_stale_invalid(self):
    with tempfile.TemporaryDirectory() as d:
        self.setup_files(d,[record('1'),record('3',lead=-1),record('4',lead=90)])
        finals={k:final(k) for k in ('1','2','3','4')}
        finals['5']=final('5',day='2026-10-15')
        finals['0']=final('0',day='2026-10-13')
        with patch('cloud.v9_tracking.all_finals',return_value=finals):
            r=summarize(d,date(2026,10,15))
        self.assertEqual(r['completed_imported_games'],4)
        self.assertEqual(r['games_with_valid_original_pregame_forecast'],2)
        self.assertEqual(r['games_without_valid_original'],2)
        self.assertEqual(r['captured_within_8_to_30_min_window'],1)
        self.assertEqual(r['capture_fraction'],.5)
        self.assertEqual(len(r['missing_originals']),1)
        self.assertEqual(len(r['late_or_invalid_originals']),1)
        self.assertEqual(r['originals_awaiting_settlement'],2)
 def test_final_scored_only_if_imported_and_prior_date(self):
    with tempfile.TemporaryDirectory() as d:
        self.setup_files(d,[record('1'),record('2')])
        with patch('cloud.v9_tracking.all_finals',return_value={'1':final('1')}):
            result=summarize(d,'2026-10-15')
        self.assertEqual(result['originals_without_imported_final'],1)
        self.assertEqual(result['completed_imported_games'],1)
 def test_empty_is_not_false_100pct_success(self):
    with tempfile.TemporaryDirectory() as d:
        with patch('cloud.v9_tracking.all_finals',return_value={}):
            result=summarize(d,'2026-10-15')
        self.assertIsNone(result['capture_fraction'])
        self.assertEqual(result['status'],'waiting_for_completed_games')
 def test_identity_check(self):
    with tempfile.TemporaryDirectory() as d:
        self.setup_files(d,[record('1')])
        with patch('cloud.v9_tracking.all_finals',return_value={'1':final('1',home='CLE')}):
            result=summarize(d,'2026-10-15')
        self.assertEqual(result['games_with_valid_original_pregame_forecast'],0)
        self.assertEqual(len(result['identity_or_result_conflicts']),1)
 def test_launch_after_october13(self):
    self.assertEqual(TRACKING_START.isoformat(),'2026-10-14')
if __name__=='__main__':unittest.main()
