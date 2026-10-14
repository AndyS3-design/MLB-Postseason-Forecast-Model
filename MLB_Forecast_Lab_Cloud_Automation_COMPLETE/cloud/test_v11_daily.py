"""V11 missed-maintenance catch-up, ET date boundary and strict pregame mode."""
import json,unittest,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from cloud.preflight import daily_maintenance_due,should_run,EASTERN
UTC=timezone.utc
class DailyCatchupTests(unittest.TestCase):
    def stamp(self,root,when):
        p=Path(root)/'cloud_records/daily_maintenance.json'
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({'successful_refresh_utc':when.isoformat()}))
    def test_missing_marker_requires_full_refresh(self):
        with tempfile.TemporaryDirectory() as t:
            now=datetime(2026,10,14,15,0,tzinfo=UTC)
            self.assertTrue(daily_maintenance_due(t,now))
            d=should_run(now,catchup=True)
            self.assertTrue(d['run']);self.assertIn('catch-up',d['reason'])
    def test_et_midnight_boundary(self):
        with tempfile.TemporaryDirectory() as t:
            now=datetime(2026,10,14,13,0,tzinfo=UTC)
            self.stamp(t,datetime(2026,10,14,2,56,tzinfo=UTC))
            self.assertTrue(daily_maintenance_due(t,now))
            self.stamp(t,datetime(2026,10,14,12,50,tzinfo=UTC))
            self.assertFalse(daily_maintenance_due(t,now))
    def test_no_games_no_new_forecast_when_current(self):
        now=datetime(2026,10,14,13,0,tzinfo=UTC)
        schedule=lambda d:{'dates':[]}
        result=should_run(now,fetcher=schedule,catchup=False)
        self.assertFalse(result['run'])
    def test_old_stale_and_corrupt_markers_require_retry(self):
        with tempfile.TemporaryDirectory() as t:
            now=datetime(2026,10,14,13,0,tzinfo=UTC)
            self.stamp(t,datetime(2026,10,13,14,0,tzinfo=UTC))
            self.assertTrue(daily_maintenance_due(t,now))
            marker=Path(t)/'cloud_records/daily_maintenance.json'
            marker.write_text('{broken')
            self.assertTrue(daily_maintenance_due(t,now))
    def test_retry_on_future_timestamp(self):
        with tempfile.TemporaryDirectory() as t:
            now=datetime(2026,10,14,13,tzinfo=UTC)
            self.stamp(t,now+timedelta(days=10))
            self.assertTrue(daily_maintenance_due(t,now))
if __name__=='__main__':unittest.main()
