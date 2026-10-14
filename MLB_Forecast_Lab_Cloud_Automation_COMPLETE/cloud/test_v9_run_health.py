"""No-silent-missing-prediction integration checks; stdlib only."""
import tempfile,json,unittest
from pathlib import Path
from cloud.v9_run_health import check,parse_expected,as_markdown

def record(game_id='123'):
    return {'game_id':game_id,'date':'2026-10-14','home':'MIL','away':'LAN',
       'forecast_created_utc':'2026-10-14T20:40:00+00:00',
       'game_start_utc':'2026-10-14T21:00:00+00:00','forecast_kind':'original_pregame'}

class RunHealthTests(unittest.TestCase):
 def test_missing_and_present(self):
    with tempfile.TemporaryDirectory() as d:
       p=Path(d)/'cloud_records/predictions';p.mkdir(parents=True)
       (p/'123.json').write_text(json.dumps(record()))
       report=check(d,['123','456'])
       self.assertEqual(report['confirmed_original_game_ids'],['123'])
       self.assertEqual(report['missing_game_ids'],['456'])
       self.assertFalse(report['passed'])
       self.assertIn('Missing originals',as_markdown(report))
 def test_rejects_late_forecast(self):
    with tempfile.TemporaryDirectory() as d:
       p=Path(d)/'cloud_records/predictions';p.mkdir(parents=True)
       late=record();late['forecast_created_utc']='2026-10-14T21:05:00+00:00'
       (p/'123.json').write_text(json.dumps(late))
       self.assertEqual(check(d,['123'])['invalid_game_ids'],['123'])
 def test_forecast_error_is_not_hidden(self):
    with tempfile.TemporaryDirectory() as d:
       p=Path(d)/'cloud_records';p.mkdir()
       (p/'last_run.json').write_text(json.dumps({'status':'finished',
          'events':[{'status':'forecast_failed','game_id':'999','error':'example'}]}))
       self.assertFalse(check(d,[])['passed'])
 def test_expected_game_ids_sanitized(self):
    self.assertEqual(parse_expected('123, 123,456'),['123','456'])
    with self.assertRaises(ValueError):parse_expected('999; rm -rf /')
 def test_no_expected_with_no_errors_is_ok(self):
    with tempfile.TemporaryDirectory() as d:
       self.assertTrue(check(d,[])['passed'])
if __name__=='__main__':unittest.main()
