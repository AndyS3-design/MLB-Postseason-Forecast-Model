"""Regression tests for MLB schedule 'api-' IDs and real box-score ID joins."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from matchup_model import enrich_games, loaded_details


class MLBAPIDetailTests(unittest.TestCase):
    def test_schedule_api_prefix_maps_to_raw_boxscore_id(self):
        with TemporaryDirectory() as tmp:
            from import_retrosheet_details import DETAIL_FIELDS
            path=Path(tmp)/'advanced_pitching_details.csv'
            rows=[dict(date='2026-08-10',home='TBA',away='CLE',side=side,
                       game_id='824621',game_num='',pitcher_id=pid,
                       sp_outs='18',sp_er='2',bp_outs='9',pitchers_used='4')
                  for side,pid in [('home','MLB-656876'),('away','MLB-656492')]]
            with path.open('w', newline='', encoding='utf-8') as handle:
                writer=csv.DictWriter(handle,fieldnames=DETAIL_FIELDS)
                writer.writeheader();writer.writerows(rows)
            details,hands,_=loaded_details(Path(tmp))
            game=dict(date='2026-08-10',home='TBA',away='CLE',
                      game_num='824621',game_id='api-824621',home_sp='',away_sp='')
            patched,matched=enrich_games([game],details,hands)
            self.assertEqual(matched,2)
            self.assertEqual(patched[0]['home_sp'],'MLB-656876')
            self.assertEqual(patched[0]['away_sp'],'MLB-656492')
            self.assertEqual(patched[0]['home_bp_outs'],9.)

    def test_two_api_doubleheaders_do_not_cross_match(self):
        from import_retrosheet_details import DETAIL_FIELDS
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'advanced_pitching_details.csv'
            rows=[dict(date='2026-07-05',home='TBA',away='CLE',side='home',
                       game_id=str(gid),pitcher_id=f'MLB-{gid}',sp_outs='15',sp_er='1')
                  for gid in (800001,800002)]
            with path.open('w', newline='', encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=DETAIL_FIELDS)
                writer.writeheader();writer.writerows(rows)
            details,hands,_=loaded_details(Path(tmp))
            games=[dict(date='2026-07-05',home='TBA',away='CLE',
                       game_id=f'api-{gid}',game_num=str(gid)) for gid in (800001,800002)]
            result,matched=enrich_games(games,details,hands)
            self.assertEqual(matched,2)
            self.assertEqual([r['home_sp'] for r in result],['MLB-800001','MLB-800002'])

    def test_unmatched_api_id_stays_unknown(self):
        game=dict(date='2026-07-05',home='TBA',away='CLE',
                  game_id='api-800001',game_num='800001')
        details={('2026-07-05','TBA','CLE','home','gid:800002'):
                 dict(pitcher_id='WRONG',sp_er='0')}
        patched,matched=enrich_games([game],details,{})
        self.assertEqual(matched,0)
        self.assertNotIn('home_sp',patched[0])

if __name__=='__main__': unittest.main()
