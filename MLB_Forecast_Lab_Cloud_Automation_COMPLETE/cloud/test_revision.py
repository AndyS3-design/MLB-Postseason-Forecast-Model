"""Before-first-pitch revision integrity and non-duplicated accuracy."""
import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from cloud import worker
class RevisionIntegrity(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,13,23,0,tzinfo=timezone.utc)
        self.g={'id':'849813','date':'2026-10-13','away':'CLE','home':'TBA',
                'status':'Scheduled','game_type':'L',
                'start_utc':(self.now+timedelta(minutes=60)).isoformat()}
        self.old={'game_id':'849813','date':'2026-10-13','away':'CLE','home':'TBA',
                'forecast_created_utc':(self.now-timedelta(minutes=90)).isoformat()}
    def test_good(self):self.assertTrue(worker.can_revise(self.g,self.now,self.old))
    def test_never_live(self):
        for status in ('In Progress','Final','Suspended'):
            self.assertFalse(worker.can_revise({**self.g,'status':status},self.now,self.old))
    def test_not_late(self):
        for minutes in (-1,0,8,11,151):
            g={**self.g,'start_utc':(self.now+timedelta(minutes=minutes)).isoformat()}
            self.assertFalse(worker.can_revise(g,self.now,self.old))
    def test_identity(self):
        self.assertFalse(worker.can_revise({**self.g,'home':'MIL'},self.now,self.old))
        self.assertFalse(worker.can_revise({**self.g,'date':'2026-10-14'},self.now,self.old))
    def test_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cloud_records/revision_requests/849813.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'kind':'one_time_pregame_revision','game_id':'849813','date':'2026-10-13'}))
            self.assertTrue(worker.revision_requested(tmp,self.g))
            self.assertFalse(worker.revision_requested(tmp,{**self.g,'date':'2026-10-14'}))
    def test_only_original_counted_for_primary_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'cloud_records'
            (state/'predictions').mkdir(parents=True);(state/'revisions').mkdir(parents=True)
            (root/'site').mkdir();(root/'site/index.html').write_text('<html/>')
            orig={**self.old,'game_start_utc':self.g['start_utc'],
                  'projected_score':{'away':3,'home':5},
                  'expected_runs':{'total':8.05},'predicted_home_win':.568,
                  'health':{'starter_pitcher_history':{'away':2,'home':1}}}
            rev={**orig,'forecast_kind':'revised_pregame',
                 'forecast_created_utc':self.now.isoformat(),
                 'projected_score':{'away':3,'home':4}}
            (state/'predictions/849813.json').write_text(json.dumps(orig))
            (state/'revisions/849813_20261013T230000Z.json').write_text(json.dumps(rev))
            with patch.object(worker,'STATE',state), patch.object(worker,'prospective_metrics',return_value={}) as m:
                worker.render_site(root,self.now,{'status':'test'})
                self.assertEqual(len(m.call_args.args[0]),1)
            data=json.loads((root/'site/data.json').read_text())
            self.assertEqual(data['predictions'][0]['forecast_kind'],'revised_pregame')
            self.assertEqual(data['predictions'][0]['original_comparison']['score']['away'],3)
            self.assertEqual(json.loads((state/'predictions/849813.json').read_text()),orig)
