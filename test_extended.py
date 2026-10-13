import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from ingest_mlb import schedule_from_response,save
from extended_eval import predict_elo,all_games
from market_backtest import analyze
from market_baseline import implied,evaluate
from manual_2025_postseason import create

class TestMLBIngest(unittest.TestCase):
    def setUp(self):
        def game(gameid,day,state,hs,as_,extra=False):
            inn=[{'home':{'runs':0},'away':{'runs':0}} for _ in range(9)]
            inn[8]['home']['runs']=hs-int(extra)
            inn[8]['away']['runs']=as_
            if extra:inn.append({'home':{'runs':1},'away':{'runs':0}})
            return {'gamePk':gameid,'officialDate':day,'gameDate':day+'T18:05:00Z',
              'gameType':'R','status':{'abstractGameState':state},
              'teams':{'home':{'team':{'id':119},'score':hs},
                       'away':{'team':{'id':158},'score':as_}},
              'linescore':{'innings':inn,'currentInning':10 if extra else 9}}
        self.schedule={'dates':[{'date':'2026-10-11','games':[
            game(100,'2026-10-11','Final',2,1,True),
            game(101,'2026-10-11','Live',4,3),
            game(102,'2026-10-12','Final',6,1)]}]}
    def test_excludes_today_and_live_and_handles_extras(self):
        got=schedule_from_response(self.schedule,'2026-10-12')
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]['home'],'LAN')
        self.assertEqual(got[0]['away'],'MIL')
        self.assertEqual(got[0]['home_final'],2)
        self.assertEqual(got[0]['home_reg'],1)
    def test_duplicate_save(self):
        rows=schedule_from_response(self.schedule,'2026-10-12')
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(save(rows+rows,Path(d)/'test.csv'),1)
    def test_actual_playoff_transcription_rows(self):
        with tempfile.TemporaryDirectory() as d:
            n=create(Path(d)/'post.csv');f=pd.read_csv(Path(d)/'post.csv')
            self.assertEqual(n,47)
            self.assertEqual(f.game_id.nunique(),47)
            self.assertEqual(set(f.year),{2025})
            self.assertTrue((f.home_final!=f.away_final).all())

class TestElo(unittest.TestCase):
    def test_current_day_score_not_used_for_other_same_day_game(self):
        def g(day,away,home,hwin):
            return {'date':pd.Timestamp(day),'year':2025,'home':home,'away':away,
                 'game_id':day+home,'game_type':'R','home_final':3 if hwin else 1,
                 'away_final':1 if hwin else 3}
        games=[g('2025-06-01','LAN','MIL',True),g('2025-06-01','BOS','NYA',True),
               g('2025-06-02','LAN','MIL',True)]
        first=predict_elo(games)
        games[0]['home_final']=0;games[0]['away_final']=10
        second=predict_elo(games)
        self.assertEqual(float(first.iloc[1].p_home_elo),float(second.iloc[1].p_home_elo))
        self.assertNotEqual(float(first.iloc[2].p_home_elo),float(second.iloc[2].p_home_elo))

class TestMarkets(unittest.TestCase):
    def setUp(self):
        self.preds=pd.DataFrame([dict(game_id='test-1',p_home_elo=.7,
            p_under_6_5_run_model=.6,actual_home_win=1,actual_under_6_5=0)])
        self.quotes=pd.DataFrame([dict(game_id='test-1',market='home_win',price_source='kalshi',
             is_executable='true',quote_timestamp_utc='2025-06-01T16:00:00Z',
             first_pitch_utc='2025-06-01T18:00:00Z',yes_ask=.55,fee_per_contract_usd=.01)])
    def test_ev_pnl(self):
        s,t=analyze(self.preds,self.quotes)
        self.assertEqual(s['n_trades'],1)
        self.assertAlmostEqual(s['net_pnl_usd'],.44)
        self.assertAlmostEqual(t.iloc[0].estimated_ev_usd_per_contract,.14)
    def test_future_quote_disallowed(self):
        q=self.quotes.copy();q.loc[0,'quote_timestamp_utc']='2025-06-01T18:01:00Z'
        with self.assertRaisesRegex(ValueError,'lookahead'): analyze(self.preds,q)
    def test_indicative_quote_disallowed(self):
        q=self.quotes.copy();q.loc[0,'is_executable']='false'
        with self.assertRaisesRegex(ValueError,'Non-executable'):analyze(self.preds,q)
    def test_stale_quote_disallowed(self):
        q=self.quotes.copy();q.loc[0,'quote_timestamp_utc']='2025-05-31T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'Stale'):analyze(self.preds,q)
    def test_wrong_game_disallowed(self):
        q=self.quotes.copy();q.loc[0,'game_id']='not-a-match'
        with self.assertRaisesRegex(ValueError,'does not match'):analyze(self.preds,q)
    def test_american_odds(self):
        self.assertAlmostEqual(implied(-150),.6)
        self.assertAlmostEqual(implied(150),.4)
        s=evaluate(self.preds,pd.DataFrame([dict(game_id='test-1',
         quote_timestamp_utc='2025-06-01T17:00:00Z',first_pitch_utc='2025-06-01T18:00:00Z',
         home_american=-150,away_american=130)]))
        self.assertEqual(s['n'],1)

if __name__=='__main__':unittest.main()
