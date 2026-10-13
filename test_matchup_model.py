"""Expanded MLB validation: strict pregame chronology, real-data scoring, detail imports."""
from __future__ import annotations
import csv,io,json,unittest,zipfile
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import numpy as np
import pandas as pd
from matchup_model import (Team,Starter,feature_frame,enrich_games,loaded_details,
    expanded_forecast,backtest_expanded,resolve_starter)
from import_retrosheet_details import parse_season_zip
from import_mlb_boxscores import outs_from_ip,pitcher_stats
from extended_eval import all_games


def match(day,h=5,a=2,home='MIL',away='LAN',hp='PITCHER_A',ap='PITCHER_B',**extra):
    return dict(date=day,year=int(day[:4]),game_num='0',game_id='game_'+day+'_'+home,
     game_type='R',home=home,away=away,home_final=h,away_final=a,
     home_sp=hp,away_sp=ap,home_pitchers_used=4,away_pitchers_used=3,
     home_manager='MGR_A',away_manager='MGR_B',home_ab=32,away_ab=33,
     home_hits=9,away_hits=7,home_walks=3,away_walks=2,
     home_hbp=0,away_hbp=1,home_sf=0,away_sf=0,
     home_2b=2,away_2b=1,home_3b=0,away_3b=0,
     home_hr=1,away_hr=0,**extra)


class ChronologyTests(unittest.TestCase):
    def test_same_day_doubleheader_game_cannot_affect_other(self):
        day='2025-06-13';one=match(day,7,1)
        two=match(day,2,5,game_num='1') if False else match(day,2,5,home='CLE',away='TBA')
        before=feature_frame([one,two]).iloc[0]
        modified=match(day,200,1,home='CLE',away='TBA')
        after=feature_frame([one,modified]).iloc[0]
        for col in ('elo_logit','offense_rpg15_diff','bullpen_used3_diff','sp_era_diff'):
            self.assertAlmostEqual(before[col],after[col])

    def test_future_and_target_outcomes_excluded(self):
        old=match('2025-06-10',4,3)
        target=match('2025-06-11',3,2)
        a=feature_frame([old,target]).iloc[-1]
        target_change=match('2025-06-11',500,0)
        b=feature_frame([old,target_change]).iloc[-1]
        for key in ['elo_logit','offense_rpg15_diff','sp_start_quality_diff','bullpen_used3_diff']:
            self.assertAlmostEqual(a[key],b[key])

    def test_pitcher_era_uses_real_starter_outs_only(self):
        st=Starter();st.record(date(2025,5,1),match('2025-05-01',10,0,home_sp_outs=18,home_sp_er=1,home_sp_k=7,home_sp_bb=1),'home',0)
        v=st.signals(date(2025,5,8))
        self.assertEqual(v['known'],1)
        self.assertLess(v['earned_era'],4.3)
        empty=Starter();empty.record(date(2025,5,1),match('2025-05-01',10,0),'home',0)
        self.assertEqual(empty.signals(date(2025,5,8))['known'],0)
        self.assertEqual(empty.signals(date(2025,5,8))['earned_era'],4.3)

    def test_bullpen_usage_is_nonnegative_lagged(self):
        t=Team();self.assertEqual(t.signals(date(2025,4,2),'')['bp_used3'],0)
        t.record(date(2025,4,1),3,5,match('2025-04-01'),'home','')
        self.assertEqual(t.signals(date(2025,4,2),'')['bp_used3'],3)
        self.assertEqual(t.signals(date(2025,4,10),'')['bp_used3'],0)

    def test_enrichment_joins_date_team_side_not_future_games(self):
        g=match('2025-05-01')
        rec={'date':'2025-05-01','home':'MIL','away':'LAN','side':'home','pitcher_id':'PITCHER_A',
             'sp_hand':'R','sp_outs':'18','sp_er':'1','sp_k':'7','sp_bb':'1','sp_hr':'0',
             'bp_outs':'9','bp_er':'2','pitchers_used':'4'}
        data,h=enrich_games([g],{('2025-05-01','MIL','LAN','home'):rec},{})
        self.assertEqual(data[0]['home_sp_outs'],18.0)
        self.assertEqual(data[0]['home_bp_outs'],9.0)
        self.assertEqual(h,1)

    def test_resolve_never_fuzzy_guesses(self):
        self.assertEqual(resolve_starter('Pitcher One',{'pitcher one':{'A'}}),'A')
        self.assertEqual(resolve_starter('Pitcher One',{'pitcher one':{'A','B'}}),'')
        self.assertEqual(resolve_starter('Pitcher X',{}),'')


class ImportTests(unittest.TestCase):
    def test_retrosheet_zip_pitches_and_directory(self):
        with TemporaryDirectory() as td:
            zp=Path(td)/'2025csvs.zip'
            def csvdata(fields,rows):
                f=io.StringIO();w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
                return f.getvalue()
            with zipfile.ZipFile(zp,'w') as z:
                z.writestr('2025gameinfo.csv',csvdata(['gid','season','date','hometeam','visteam'],[
                    dict(gid='MIL202506130',season='2025',date='2025-06-13',hometeam='MIL',visteam='LAN')]))
                z.writestr('2025pitching.csv',csvdata(['gid','id','team','p_seq','stattype','p_ipouts','p_er','p_k','p_w','p_hr'],[
                    dict(gid='MIL202506130',id='pitch_home',team='MIL',p_seq='1',stattype='value',p_ipouts='15',p_er='1',p_k='8',p_w='1',p_hr='0'),
                    dict(gid='MIL202506130',id='relief_home',team='MIL',p_seq='2',stattype='value',p_ipouts='12',p_er='2',p_k='5',p_w='1',p_hr='1'),
                    dict(gid='MIL202506130',id='pitch_away',team='LAN',p_seq='1',stattype='value',p_ipouts='18',p_er='4',p_k='4',p_w='3',p_hr='1')]))
                z.writestr('2025allplayers.csv',csvdata(['id','first','last','throw','team','season'],[
                    dict(id='pitch_home',first='Pitcher',last='One',throw='R',team='MIL',season='2025'),
                    dict(id='pitch_away',first='Pitcher',last='Two',throw='L',team='LAN',season='2025')]))
            rows,people,summary=parse_season_zip(zp,2025)
            self.assertEqual(len(rows),2)
            home=next(r for r in rows if r['side']=='home')
            self.assertEqual(home['sp_outs'],15)
            self.assertEqual(home['bp_outs'],12)
            self.assertEqual(home['sp_hand'],'R')
            self.assertEqual(home['pitchers_used'],2)

    def test_mlb_innings_outs_not_decimal(self):
        self.assertEqual(outs_from_ip('6.1'),19)
        self.assertEqual(outs_from_ip('6.2'),20)
        self.assertIsNone(outs_from_ip('6.3'))

    def test_mlb_boxscore_extraction(self):
        def player(pid,ip,er,hand):
            return {'person':{'id':pid,'fullName':'Pitcher '+str(pid),'pitchHand':{'code':hand}},
                 'stats':{'pitching':{'inningsPitched':ip,'earnedRuns':er,'strikeOuts':5,'baseOnBalls':2}}}
        payload={'teams':{
            'home':{'pitchers':[10,11],'players':{'ID10':player(10,'5.2',2,'R'),'ID11':player(11,'3.1',0,'L')}},
            'away':{'pitchers':[20],'players':{'ID20':player(20,'8.0',3,'L')}}}}
        row,person=pitcher_stats(payload,'home',{'date':'2026-05-01','home':'MIL','away':'LAN'})
        self.assertEqual(row['sp_outs'],17)
        self.assertEqual(row['bp_outs'],10)
        self.assertEqual(row['pitchers_used'],2)
        self.assertEqual(row['sp_hand'],'R')
        self.assertEqual(person['pitcher_id'],'MLB-10')


class HistoricalSmoke(unittest.TestCase):
    def test_actual_holdout_and_cutoff(self):
        base=Path(__file__).parent/'data'
        if not (base/'GL2023.TXT').exists():self.skipTest('Real logs absent')
        games=all_games(base,True)
        result,model,frame,hands,directory=backtest_expanded(games,base)
        self.assertEqual(result['splits']['2025_regular']['n'],2425)
        self.assertLess(result['splits']['2025_regular']['expanded']['brier'],.30)
        prediction=expanded_forecast(games,'2025-10-12','MIL','LAN',model,hands)
        self.assertTrue(0<prediction['p_home_expanded']<1)
        # Future games cannot affect predictions on October 12, 2025.
        later=match('2026-10-13',100,0)
        prediction2=expanded_forecast(games+[later],'2025-10-12','MIL','LAN',model,hands)
        self.assertEqual(prediction['p_home_expanded'],prediction2['p_home_expanded'])


if __name__=='__main__':unittest.main()
