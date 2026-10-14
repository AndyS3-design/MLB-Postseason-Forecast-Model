"""Offline V17 deployment/schedule, official lineup hand, and evaluation audit."""
import unittest
from datetime import datetime,timedelta,timezone
from cloud.preflight import find_approaching_games
from cloud.v17_prospective import score_originals
from v4_sources import capture_official_pregame

UTC=timezone.utc
START=datetime(2026,10,14,23,30,tzinfo=UTC)
def raw(start,state='Scheduled'):
    return {'gamePk':849811,'gameType':'L','gameDate':start.isoformat(),
            'status':{'detailedState':state}}

def original(game_id='10',score=5,lead=20):
    return {'game_id':game_id,'forecast_kind':'original_pregame',
            'forecast_created_utc':(START-timedelta(minutes=lead)).isoformat(),
            'game_start_utc':START.isoformat(),'official_final':{'home':3,'away':2},
            'expected_runs':{'total':6.},'predicted_home_win':.6,
            'elo_home_win':.5,'model_version':'v17','total_distribution':{'4':.25,'5':.5,'8':.25}}


class V17Tests(unittest.TestCase):
    def test_wide_gate_retries_late_but_never_after_start(self):
        payload=lambda day:{'dates':[{'games':[raw(START)]}]}
        self.assertEqual(len(find_approaching_games(START-timedelta(minutes=37),payload)),1)
        self.assertEqual(len(find_approaching_games(START-timedelta(minutes=12),payload)),1)
        self.assertEqual(find_approaching_games(START-timedelta(minutes=8),payload),[])
        self.assertEqual(find_approaching_games(START,payload),[])
        self.assertEqual(find_approaching_games(START-timedelta(minutes=20),
            lambda d:{'dates':[{'games':[raw(START,'In Progress')]}]}),[])

    def test_official_same_request_handedness_fallback(self):
        ids=list(range(101,110))
        feed={'gameData':{'status':{'detailedState':'Pre-Game','abstractGameState':'Preview'},
               'players':{'ID'+str(i):{'id':i,'fullName':f'Batter {i}',
                            'batSide':{'code':'L' if i%2 else 'R'}} for i in ids}},
              'liveData':{'boxscore':{'teams':{'home':{'battingOrder':ids,
                 'players':{'ID'+str(i):{'person':{'id':i,'fullName':f'Batter {i}'}} for i in ids}},
                 'away':{'battingOrder':ids,
                 'players':{'ID'+str(i):{'person':{'id':i}} for i in ids}}}}}}
        snap=capture_official_pregame('849811',START.isoformat(),
             now=START-timedelta(hours=1),fetcher=lambda url:feed)
        self.assertTrue(all(snap['is_official_lineup'].values()))
        self.assertEqual(snap['confirmed_lineups']['home'][0]['batting_hand'],'L')
        self.assertEqual(snap['confirmed_lineups']['away'][1]['batting_hand'],'R')
        self.assertEqual(snap['confirmed_lineups']['away'][0]['name'],'Batter 101')

    def test_frozen_originals_not_duplicate_previews(self):
        rec=original()
        preview={**rec,'forecast_kind':'preliminary_pregame','game_id':'extra'}
        revised={**rec,'forecast_kind':'revised_pregame','game_id':'revised'}
        out=score_originals([rec,preview,revised])
        self.assertEqual(out['unique_originals'],1)
        self.assertEqual(out['settled_distribution_complete_games'],1)
        self.assertEqual(out['winner']['brier'],.16)
        self.assertEqual(out['winner']['elo_brier_same_games'],.25)
        self.assertEqual(out['combined_runs']['mae'],1)
        self.assertEqual(out['total_lines']['3.5']['under_brier'],0)
        self.assertEqual(out['total_lines']['4.5']['under_brier'],.0625)
        self.assertEqual(out['total_lines']['5.5']['under_brier'],.0625)
        self.assertEqual(out['total_lines']['6.5']['under_brier'],.0625)
        self.assertEqual(out['model_versions'],{'v17':1})
        self.assertEqual(sum(v['n'] for v in out['winner']['calibration']),1)

    def test_bad_distribution_not_reported_as_calibrated(self):
        broken={**original('1'),'total_distribution':{'0':.5}}
        out=score_originals([broken])
        self.assertEqual(out['settled_distribution_complete_games'],0)
        self.assertEqual(out['excluded']['missing_or_invalid_full_distribution'],1)
        with self.assertRaises(ValueError):
            score_originals([original('2'),original('2')])

    def test_historical_after_first_pitch_excluded(self):
        x=original('late',lead=-4)
        out=score_originals([x])
        self.assertEqual(out['unique_originals'],0)

if __name__=='__main__':
    unittest.main()
