"""V15 official two-lineup refresh: full orders required, no frozen records replaced."""
import json, tempfile, unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch

from cloud import worker
from cloud.test_v12_two_stage import EARLY, FINAL, match, model_output


def lineup_snapshot(both=True):
    players={side:[{'id':1000+i+(100 if side=='home' else 0),
                    'name':f'{side}-{i+1}','batting_hand':'R'} for i in range(9)]
             for side in ('home','away')}
    if not both:players['away']=players['away'][:8]
    return {'game_id':'20261014','captured_utc':'2026-10-14T15:00:00+00:00',
       'source':'MLB Stats API pregame live feed',
       'is_official_lineup':{'home':True,'away':both},
       'confirmed_lineups':players}


class LineupRefreshTests(unittest.TestCase):
    def test_official_lineup_only_then_final_remains_independent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'site').mkdir()
            (root/'site/index.html').write_text('placeholder')
            g=match()
            early=EARLY
            prepared=root/'cloud_records/preliminary/20261014.json'
            request=root/'cloud_records/lineup_refresh_requests/20261014.json'
            request.parent.mkdir(parents=True,exist_ok=True)
            request.write_text(json.dumps({'game_id':'20261014','date':g['date'],
                     'kind':'one_time_confirmed_lineup_refresh'}))
            snapshots=[None,lineup_snapshot(False),lineup_snapshot(),lineup_snapshot()]
            old=model_output(.58)
            confirmed=model_output(.54);confirmed['model_version']=worker.VERSION
            final=model_output(.57);final['model_version']=worker.VERSION
            with patch.object(worker,'STATE',root/'cloud_records'),\
                 patch.object(worker,'game_evidence',side_effect=snapshots),\
                 patch.object(worker,'generate',side_effect=[old,confirmed,final]),\
                 patch.object(worker,'team_indices',return_value={'teams':{}}):
                first=worker.store_pregame(g,early,[],root,{'enriched':[]},preliminary=True)
                self.assertEqual(first['status'],'preliminary_saved')
                frozen=prepared.read_bytes()
                empty=worker.store_pregame(g,early+timedelta(minutes=5),[],root,
                                          {'enriched':[]},lineup_update=True)
                self.assertEqual(empty['status'],'lineup_refresh_waiting_for_both_official_orders')
                self.assertEqual(len(list((root/'cloud_records/lineup_previews').glob('*.json'))),0)
                result=worker.store_pregame(g,early+timedelta(minutes=10),[],
                                            root,{'enriched':[]},lineup_update=True)
                self.assertEqual(result['status'],'lineup_confirmed_saved')
                saved=list((root/'cloud_records/lineup_previews').glob('*.json'))
                self.assertEqual(len(saved),1)
                j=json.loads(saved[0].read_text())
                self.assertEqual(j['forecast_kind'],'lineup_confirmed_pregame')
                self.assertEqual(j['model_version'],worker.VERSION)
                self.assertTrue(all(j['health']['lineups_confirmed'].values()))
                self.assertEqual(len(j['lineup_evidence']['confirmed_lineups']['away']),9)
                self.assertEqual(prepared.read_bytes(),frozen)
                self.assertEqual(worker.store_pregame(g,early+timedelta(minutes=12),[],
                    root,{'enriched':[]},lineup_update=True)['status'],'lineup_refresh_already_saved')
                self.assertEqual(worker.store_pregame(g,FINAL,[],root,
                    {'enriched':[]},lineup_update=True)['status'],'lineup_refresh_too_late')
                settled=worker.store_pregame(g,FINAL,[],root,{'enriched':[]})
                self.assertEqual(settled['status'],'saved')
                self.assertEqual(prepared.read_bytes(),frozen)
                worker.render_site(root,FINAL,{'status':'test'})
                site=json.loads((root/'site/data.json').read_text())
                self.assertEqual([x['forecast_kind'] for x in site['predictions']],
                  ['original_pregame','lineup_confirmed_pregame','preliminary_pregame'])
                self.assertEqual(site['model_health']['coverage']['original_forecasts'],1)

    def test_no_request_or_wrong_identity_disallowed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            g=match()
            preview={'game_id':g['id'],'home':g['home'],'away':g['away'],'date':g['date']}
            self.assertFalse(worker.lineup_refresh_requested(root,g,preview))
            q=root/'cloud_records/lineup_refresh_requests/20261014.json'
            q.parent.mkdir(parents=True)
            q.write_text(json.dumps({'kind':'one_time_confirmed_lineup_refresh',
                'game_id':'20261014','date':g['date']}))
            self.assertFalse(worker.lineup_refresh_requested(root,{**g,'away':'CHA'},preview))
            self.assertTrue(worker.lineup_refresh_requested(root,g,preview))

if __name__=='__main__':unittest.main()
