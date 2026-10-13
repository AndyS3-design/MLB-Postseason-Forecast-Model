"""Focused V4 invariant and anti-leakage tests. All fixtures synthetic."""
from __future__ import annotations
import json,math,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from v4_sources import (capture_official_pregame,batter_history,lineup_factor,relief_snapshot,
                        pitcher_snapshot,scenario_weather)
from v4_simulation import play_games,summarize,seed_for
from v4_log import freeze
from v4_matchup_core import historical_team_rows,pregame_rows


def match(side='home',id=123):
    return dict(id=str(id),home='LAN',away='MIL',home_name='Dodgers',away_name='Brewers')

class TestPregame(unittest.TestCase):
    def test_refuses_late_feed_before_network(self):
        now=datetime(2026,10,13,20,0,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):capture_official_pregame('123','2026-10-13T19:00:00Z',now=now,
               fetcher=lambda x:self.fail('should never fetch after start'))

    def test_refuses_live_flag_even_before_schedule(self):
        now=datetime(2026,10,13,18,0,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):capture_official_pregame('123','2026-10-13T19:00:00Z',now=now,
         fetcher=lambda x:dict(gameData=dict(status=dict(abstractGameState='Live')),liveData={}))

    def test_valid_official_pregame_lineup(self):
        now=datetime(2026,10,13,18,0,tzinfo=timezone.utc)
        team=dict(battingOrder=list(range(100,109)),
          players={'ID'+str(k):{'person':dict(id=k,fullName=f'Player {k}',batSide={'code':'R'})} for k in range(100,109)},
          bullpen=[222,333])
        raw={'gameData':{'status':{'abstractGameState':'Preview'},'venue':{'name':'Test Park'}},
             'liveData':{'boxscore':{'teams':{'home':team,'away':team}}}}
        result=capture_official_pregame('123','2026-10-13T19:00:00Z',now=now,fetcher=lambda x:raw)
        self.assertTrue(result['is_official_lineup']['home'])
        self.assertEqual(result['confirmed_lineups']['away'][0]['id'],100)

    def test_manual_pitcher_overrides_not_data(self):
        self.assertEqual(lineup_factor([],[])['factor'],1)
        self.assertEqual(scenario_weather(100,20,'out',roof_closed=True)['factor'],1)
        self.assertTrue(.85<=scenario_weather(100,30,'out')['factor']<=1.15)

    def test_future_hits_cannot_leak(self):
        prior=[({'date':'2026-10-01','home':'LAN','away':'MIL'},
           {'teams':{'home':{'players':{'ID10':{'stats':{'batting':{'atBats':4,'hits':4,'homeRuns':4}}}}}}}),
         ({'date':'2026-10-17','home':'LAN','away':'MIL'},
           {'teams':{'home':{'players':{'ID10':{'stats':{'batting':{'atBats':4,'hits':0,'homeRuns':0}}}}}}})]
        result=batter_history(prior,'LAN',[10],'2026-10-13')
        self.assertEqual(result[0]['observed_pa'],4)

    def test_pitcher_strict_cutoff(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            (d/'advanced_pitching_details.csv').write_text('date,pitcher_id,sp_outs,sp_er\n2026-10-11,MLB-1,18,0\n2026-10-13,MLB-1,18,10\n')
            snapshot=pitcher_snapshot(d,'MLB-1','2026-10-13')
            self.assertEqual(snapshot['known'],1)
            self.assertLess(snapshot['era'],4.35)

    def test_reliever_fatigue_is_prior_only(self):
        def game(day,pitches):
            pitchers=[11,22];players={'ID22':{'stats':{'pitching':{'inningsPitched':'1.0','earnedRuns':1,
                'numberOfPitches':pitches}},'person':{'fullName':'Reliever'}}}
            return ({'date':day,'home':'LAN','away':'MIL'},
                {'teams':{'home':{'pitchers':pitchers,'players':players},'away':{}}})
        prior=[game('2026-10-11',80),game('2026-10-13',4)]
        out=relief_snapshot(prior,'LAN','2026-10-13',[22])
        self.assertTrue(out['profiles'][0]['likely_fatigued'])

class TestSimulation(unittest.TestCase):
    def test_distribution_sums(self):
        a=play_games(5,3,10000,seed=42)
        s=summarize(a)
        self.assertTrue(np.all(a['home_final']!=a['away_final']))
        self.assertAlmostEqual(s['home_win_probability']+s['away_win_probability'],1)
        self.assertAlmostEqual(s['under_6_5_probability']+s['over_6_5_probability'],1)
        self.assertGreater(s['total_expected_runs'],0)

    def test_consistent_seed(self):
        x=play_games(4.1,4.1,n=500,seed=12)
        y=play_games(4.1,4.1,n=500,seed=12)
        self.assertTrue(np.array_equal(x['home_final'],y['home_final']))
        self.assertNotEqual(seed_for('a','v4'),seed_for('b','v4'))

    def test_separate_matchups_have_different_scoring(self):
        a=summarize(play_games(5.7,2.5,n=30000,seed=9))
        b=summarize(play_games(2.5,5.7,n=30000,seed=9))
        self.assertGreater(a['home_win_probability'],.6)
        self.assertLess(b['home_win_probability'],.4)

    def test_wind_scenario_moves_totals(self):
        x=summarize(play_games(4,4,n=30000,seed=2))
        y=summarize(play_games(4,4,n=30000,seed=2,weather_factor=1.14))
        self.assertGreater(y['total_expected_runs'],x['total_expected_runs'])

    def test_full_game_extras_no_ties(self):
        out=play_games(1.1,1.1,n=1000,seed=16,postseason=True)
        self.assertTrue(np.all(out['home_final']!=out['away_final']))

class TestFrozenLog(unittest.TestCase):
    def setUp(self):
        self.result={'match':match(),'model_version':'4.0','home':'LAN','away':'MIL',
          'date':'2026-10-13','forecast':{'home_win_probability':.5},
          'training':{},'personnel':{'home':{'lineup':[]},'away':{'lineup':[]}},
          'data_gaps':[],'adjustments':{},'provenance':{}}
    def test_freeze_only_before_start_and_once(self):
        now=datetime(2026,10,13,18,0,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'records.jsonl'
            rec=freeze(self.result,'2026-10-13T19:00:00Z',now=now,destination=dest)
            self.assertIn('record_hash_sha256',rec)
            with self.assertRaises(ValueError):freeze(self.result,'2026-10-13T19:00:00Z',now=now,destination=dest)
    def test_block_late(self):
        now=datetime(2026,10,13,20,0,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):freeze(self.result,'2026-10-13T19:00:00Z',now=now,destination=Path(temp)/'j')

class TestChronology(unittest.TestCase):
    def test_same_day_outcome_not_used_as_feature(self):
        def g(day,a,b):return dict(date=pd.Timestamp(day),year=2023,game_num='0',game_id=day,
            game_type='R',home='LAN',away='MIL',home_final=a,away_final=b,home_reg=a,away_reg=b)
        h=[g('2023-05-01',1,2),g('2023-05-02',3,4)]
        base=pregame_rows(h,'2023-05-02','LAN','MIL')
        altered=pregame_rows(h[:-1]+[g('2023-05-02',20,1)],'2023-05-02','LAN','MIL')
        self.assertEqual(float(base.iloc[0].own_rpg15),float(altered.iloc[0].own_rpg15))

if __name__=='__main__':unittest.main()
