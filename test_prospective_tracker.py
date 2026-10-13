"""Regression tests for live timing, audit integrity and hypothetical-market accounting."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone,date
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from prospective_tracker import (parse_time,timestamp,require_pregame,paths,append_record,read_log,
    compress_matrix,decompress_matrix,add_quote,lock_paper_entry,settle,
    parse_official_finals,normal_id,bootstrap_diff,analysis,freeze_game,
    fingerprint,data_fingerprint,model_probability)

NOW=datetime(2026,10,12,22,30,tzinfo=timezone.utc)
START=datetime(2026,10,13,0,0,tzinfo=timezone.utc)


def fixture_match(gid='888888'):
    return {'id':gid,'date':'2026-10-12','home':'TBA','away':'CLE',
            'home_name':'Tampa Bay Rays','away_name':'Cleveland Guardians',
            'home_pitcher':'Drew Rasmussen','away_pitcher':'Foster Griffin',
            'home_pitcher_id':'MLB-656876','away_pitcher_id':'MLB-656492',
            'status':'Pre-Game','start_utc':timestamp(START)}


def small_forecast(gid='888888'):
    mat=np.zeros((12,12));mat[3,2]=.6;mat[2,3]=.4
    summary={'under_6_5_probability':1.0,'representative_favorite_score':{'home_runs':3,'away_runs':2,'probability':.6},
             'expected_home_runs':2.6,'expected_away_runs':2.4,'total_80pct_interval':[5,5],'total_90pct_interval':[5,5]}
    return {'forecast_id':'f'+gid,'game_id':gid,'game_date':'2026-10-12',
            'elo_home_win_probability':.6,'elo_away_win_probability':.4,
            'first_pitch_utc':timestamp(START),'created_at_utc':timestamp(NOW),
            'matchup':{'home':'TBA','away':'CLE'},
            'scoring_distributions':{name:compress_matrix(mat) for name in ('poisson','validated_nb','wide_nb','constant_nb')},
            'scoring_summaries':{name:summary for name in ('poisson','validated_nb','wide_nb','constant_nb')}}


class ProspectiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Path(self.tmp.name)
        self.fs=append_record(paths(self.store)['forecasts'],small_forecast())

    def tearDown(self):self.tmp.cleanup()

    def test_require_pregame_valid(self):
        t,k=require_pregame(fixture_match(),NOW)
        self.assertEqual(k,START)
        self.assertEqual(t,NOW)

    def test_reject_after_start_even_when_status_pregame(self):
        with self.assertRaisesRegex(ValueError,'passed'):
            require_pregame(fixture_match(),START)

    def test_reject_game_in_progress_even_before_scheduled(self):
        g=fixture_match();g['status']='In Progress'
        with self.assertRaises(ValueError):require_pregame(g,NOW)

    def test_reject_missing_or_naive_start(self):
        g=fixture_match();g['start_utc']='2026-10-13T00:00:00'
        with self.assertRaisesRegex(ValueError,'UTC-aware'):
            require_pregame(g,NOW)

    def test_append_only_with_hash_chain(self):
        q=append_record(paths(self.store)['quotes'],{'test':'a'})
        self.assertEqual(len(read_log(paths(self.store)['quotes'])),1)
        self.assertEqual(read_log(paths(self.store)['quotes'])[0]['record_hash'],q['record_hash'])
        txt=paths(self.store)['quotes'].read_text()
        paths(self.store)['quotes'].write_text(txt.replace('"a"','"b"'))
        with self.assertRaisesRegex(ValueError,'inconsistent'):
            read_log(paths(self.store)['quotes'])

    def test_matrix_roundtrip(self):
        a=np.eye(32)/32
        self.assertTrue(np.allclose(decompress_matrix(compress_matrix(a)),a))

    def test_non_executable_quote_rejected(self):
        with self.assertRaisesRegex(ValueError,'Attest'):
            add_quote(self.fs['forecast_id'],'home_win',55,2,False,self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])

    def test_quote_after_kickoff_rejected(self):
        with self.assertRaisesRegex(ValueError,'after scheduled'):
            add_quote(self.fs['forecast_id'],'home_win',55,2,True,self.store,START)

    def test_market_quotes_fee_and_no_fill(self):
        q=add_quote(self.fs['forecast_id'],'home_win',55,2,True,self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])
        self.assertAlmostEqual(q['implied_break_even_with_fee'],.57)
        self.assertAlmostEqual(q['modeled_ev_per_1usd_contract'],.03)
        self.assertTrue(q['not_a_fill'])
        self.assertTrue(q['is_user_attested'])

    def test_reject_fee_over_a_dollar(self):
        with self.assertRaises(ValueError):add_quote(self.fs['forecast_id'],'home_win',98,4,True,self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])

    def test_paper_entry_only_before_kickoff_and_only_one_per_game(self):
        q=add_quote(self.fs['forecast_id'],'home_win',55,2,True,self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])
        b=lock_paper_entry(q['quote_id'],self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])
        self.assertEqual(b['contracts'],1)
        with self.assertRaisesRegex(ValueError,'Only one'):
            lock_paper_entry(q['quote_id'],self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])

    def test_parse_official_final_rejects_missing_score(self):
        payload={'dates':[{'date':'2026-10-12','games':[{
            'gamePk':888888,'officialDate':'2026-10-12','status':{'abstractGameState':'Final'},
            'teams':{'home':{'team':{'id':139}},'away':{'team':{'id':114},'score':2}}
        }]}]}
        self.assertEqual(parse_official_finals(payload,date(2026,10,12)),{})
        payload['dates'][0]['games'][0]['teams']['home']['score']=3
        self.assertEqual(parse_official_finals(payload,date(2026,10,12))['888888']['home_final'],3)

    def test_graded_market_is_paper_not_real(self):
        q=add_quote(self.fs['forecast_id'],'home_win',55,2,True,self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])
        lock_paper_entry(q['quote_id'],self.store,NOW,refresh_fetcher=lambda day:[fixture_match()])
        def fake_final(day):
            return {'888888':{'game_id':'888888','game_date':'2026-10-12',
                              'home':'TBA','away':'CLE','home_final':3,'away_final':2}}
        saved=settle('2026-10-12',self.store,fake_final,START+timedelta(hours=4))
        self.assertEqual(len(saved),1)
        result,rows=analysis(self.store)
        self.assertEqual(result['settled_games'],1)
        self.assertAlmostEqual(result['paper_trades']['hypothetical_pnl_usd'],.43)
        self.assertFalse(result['paper_trades']['real_money_claim'])
        self.assertIsNone(result['paired_intervals']['wide_nb_minus_validated_nb']['exact_log_loss'])
        self.assertEqual(len(settle('2026-10-12',self.store,fake_final,START+timedelta(hours=4))),0)

    def test_pair_bootstrap_require_minimum_sample(self):
        self.assertIsNone(bootstrap_diff([.05]*10,['2026-10-12']*10))
        ci=bootstrap_diff([.05]*40,[f'2026-08-{i%20+1:02d}' for i in range(40)])
        self.assertAlmostEqual(ci[0],.05)
        self.assertAlmostEqual(ci[1],.05)

    def test_identifiers(self):
        self.assertEqual(normal_id('api-824621'),'824621')
        with self.assertRaises(ValueError):normal_id('dodgers-brewers')

    def test_require_official_refetch_no_retroactive_freeze(self):
        from prospective_tracker import freeze_game
        match=fixture_match('999999')
        # A candidate game already started: log must reject without computing a model.
        with self.assertRaisesRegex(ValueError,'passed'):
            freeze_game(match,[],None,self.store,START,refresh_fetcher=lambda day:[match])

    def test_fingerprint(self):
        from pathlib import Path
        root=Path(__file__).resolve().parent
        self.assertEqual(len(fingerprint(root)),64)
        self.assertEqual(len(data_fingerprint(root/'data')),64)

if __name__=='__main__':unittest.main()
