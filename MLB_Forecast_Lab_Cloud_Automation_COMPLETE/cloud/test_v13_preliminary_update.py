"""One-time V13 preview update: real re-simulation, immutable old preview, final still due."""
import json,tempfile,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from cloud import worker
from cloud.test_v12_two_stage import match,EARLY,FINAL,model_output

class PreliminaryUpdateTests(unittest.TestCase):
 def test_recalculated_preview_is_independent_and_final_remains_available(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   (root/'site').mkdir()
   (root/'site/index.html').write_text('placeholder')
   g=match()
   from_old=model_output(.60)
   newest=model_output(.51);newest['model_version']=worker.VERSION
   final=model_output(.52);final['model_version']=worker.VERSION
   args=(g,EARLY,[],root,{'enriched':[]})
   with patch.object(worker,'STATE',root/'cloud_records'),\
        patch.object(worker,'game_evidence',return_value=None),\
        patch.object(worker,'generate',side_effect=[from_old,newest,final]),\
        patch.object(worker,'team_indices',return_value={'teams':{}}):
    a=worker.store_pregame(*args,preliminary=True)
    self.assertEqual(a['status'],'preliminary_saved')
    first=root/'cloud_records/preliminary/20261014.json'
    bytes_before=first.read_bytes()
    self.assertEqual(worker.store_pregame(g,EARLY+timedelta(minutes=5),[],root,
       {'enriched':[]},preliminary_update=True)['status'],'preliminary_update_unrequested')
    request=root/'cloud_records/preliminary_update_requests/20261014.json'
    request.parent.mkdir(parents=True,exist_ok=True)
    request.write_text(json.dumps({'game_id':'20261014','date':g['date'],
         'kind':'one_time_preliminary_update','required_model_version':worker.VERSION}))
    new_time=EARLY+timedelta(minutes=5)
    b=worker.store_pregame(g,new_time,[],root,{'enriched':[]},preliminary_update=True)
    self.assertEqual(b['status'],'preliminary_updated_saved')
    new_files=list((root/'cloud_records/preliminary_revisions').glob('20261014_*.json'))
    self.assertEqual(len(new_files),1)
    self.assertEqual(first.read_bytes(),bytes_before)
    new_record=json.loads(new_files[0].read_text())
    self.assertEqual(new_record['forecast_kind'],'preliminary_updated_pregame')
    self.assertEqual(new_record['original_forecast_created_utc'],
                    json.loads(first.read_text())['forecast_created_utc'])
    self.assertEqual(new_record['model_version'],worker.VERSION)
    self.assertEqual(worker.store_pregame(g,new_time,[],root,
        {'enriched':[]},preliminary_update=True)['status'],'preliminary_update_already_saved')
    self.assertEqual(worker.store_pregame(g,FINAL,[],root,
        {'enriched':[]},preliminary_update=True)['status'],'preliminary_update_too_late')
    final_result=worker.store_pregame(g,FINAL,[],root,{'enriched':[]})
    self.assertEqual(final_result['status'],'saved')
    self.assertEqual(first.read_bytes(),bytes_before)
    worker.render_site(root,FINAL,{'status':'test'})
    published=json.loads((root/'site/data.json').read_text())
    self.assertEqual([p['forecast_kind'] for p in published['predictions']],
       ['original_pregame','preliminary_updated_pregame','preliminary_pregame'])
    self.assertEqual(published['model_health']['coverage']['original_forecasts'],1)
    self.assertEqual(published['two_stage_comparison']['preliminary_count'],1)
    self.assertEqual(published['two_stage_comparison']['paired_settled_games'],0)

 def test_update_rejects_wrong_game_or_model_and_past_start(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);g=match()
   p=root/'cloud_records/preliminary/20261014.json'
   p.parent.mkdir(parents=True)
   p.write_text(json.dumps({'model_version':'old','game_id':'20261014',
      'date':g['date'],'home':g['home'],'away':g['away']}))
   q=root/'cloud_records/preliminary_update_requests/20261014.json'
   q.parent.mkdir(parents=True)
   q.write_text(json.dumps({'kind':'one_time_preliminary_update',
        'game_id':'20261014','date':g['date'],'required_model_version':'incorrect'}))
   self.assertFalse(worker.preliminary_update_requested(root,g,json.loads(p.read_text())))
   self.assertFalse(worker.can_preliminary(g,FINAL))
   q.write_text(json.dumps({'kind':'one_time_preliminary_update',
        'game_id':'20261014','date':g['date'],'required_model_version':worker.VERSION}))
   self.assertFalse(worker.preliminary_update_requested(root,{**g,'home':'CHA'},json.loads(p.read_text())))

if __name__=='__main__':unittest.main()
