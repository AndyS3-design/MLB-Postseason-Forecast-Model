import unittest
from datetime import datetime,timezone,timedelta
import numpy as np
from v4_simulation import play_games,summarize
from v5_totals import probabilities_for_line,representative_score,fair_decimal,american_to_decimal,decimal_to_american,expected_unit_roi,kalshi_contract_edge,normalized_market_probs
from v5_markets import PROVIDERS,find_event,normalize_event_markets,totals_table_for_line,consensus_for_line,fetch_book_odds,fetch_dfs_props,normalize_dfs_props
from v5_pregame import parse_mlb_weather,is_verified_pregame
from v5_quote_log import record_manual_quote

ST=datetime(2026,10,13,23,0,tzinfo=timezone.utc)

class TotalsAndSimulationTests(unittest.TestCase):
 def test_pmf_and_arbitrary_lines(self):
  draw=play_games(4.2,3.7,n=1200,seed=108,postseason=True)
  res=summarize(draw)
  self.assertAlmostEqual(sum(res['total_pmf'].values()),1,places=8)
  p=probabilities_for_line(res['total_pmf'],6.5)
  self.assertAlmostEqual(p['over']+p['under'],1,places=8)
  self.assertAlmostEqual(p['under'],res['under_6_5_probability'],places=8)
  pint=probabilities_for_line(res['total_pmf'],7.)
  self.assertAlmostEqual(sum(pint[k] for k in ('over','under','push')),1,places=8)
  self.assertGreater(pint['push'],0)
  self.assertEqual((res['representative_score']['home']>res['representative_score']['away']),res['home_win_probability']>=.5)
 def test_probabilities_no_synthetic_interpolation(self):
  with self.assertRaises(ValueError):probabilities_for_line({'5':.4,'6':.3,'7':.1},6.5)
  with self.assertRaises(ValueError):probabilities_for_line({'5':1.},-1)
 def test_one_score_fallback(self):
  raw={'home_win_probability':.54,'modal_exact_scores':[{'home':2,'away':3,'probability':.04},{'home':4,'away':3,'probability':.033}]}
  self.assertEqual(representative_score(raw)['home'],4)
 def test_pricing_with_push(self):
  self.assertAlmostEqual(fair_decimal(.4,.2),2)
  self.assertAlmostEqual(expected_unit_roi(.4,.2,2),0)
  self.assertAlmostEqual(american_to_decimal(-110),1+100/110)
  self.assertEqual(decimal_to_american(2.),100)
  self.assertAlmostEqual(kalshi_contract_edge(.62,58,1.5)['expected_dollars_per_contract'],.025)
  self.assertAlmostEqual(normalized_market_probs(1.9,1.9)['over'],.5)

class OddsAndFeedTests(unittest.TestCase):
 def setUp(self):
  self.payload=[{'id':'event123456','commence_time':ST.isoformat(),'home_team':'Milwaukee Brewers','away_team':'Los Angeles Dodgers','bookmakers':[
    {'key':'hardrockbet_fl','last_update':(ST-timedelta(minutes=2)).isoformat(),'markets':[
      {'key':'totals','outcomes':[{'name':'Over','point':6.5,'price':1.9},{'name':'Under','point':6.5,'price':1.9},
        {'name':'Over','point':7.5,'price':2.05},{'name':'Under','point':7.5,'price':1.73}]},
      {'key':'h2h','outcomes':[{'name':'Milwaukee Brewers','price':1.8},{'name':'Los Angeles Dodgers','price':2.01}]}]},
    {'key':'draftkings','last_update':(ST-timedelta(minutes=1)).isoformat(),'markets':[
      {'key':'totals','outcomes':[{'name':'Over','point':6.5,'price':1.91},{'name':'Under','point':6.5,'price':1.91}]}]},
    {'key':'underdog','last_update':ST.isoformat(),'markets':[{'key':'totals','outcomes':[{'name':'Over','point':6.5,'price':1.5}]}]},
  ]}]
 def test_match_requires_both_teams_and_start(self):
  self.assertIsNotNone(find_event(self.payload,'Los Angeles Dodgers','Milwaukee Brewers',ST.isoformat()))
  self.assertIsNone(find_event(self.payload,'Los Angeles Dodgers','Cleveland Guardians',ST.isoformat()))
  self.assertIsNone(find_event(self.payload,'Los Angeles Dodgers','Milwaukee Brewers',(ST+timedelta(hours=5)).isoformat()))
 def test_exact_lines_exclude_dfs(self):
  game=find_event(self.payload,'Los Angeles Dodgers','Milwaukee Brewers',ST.isoformat())
  totals,ml=normalize_event_markets(game,now=ST)
  self.assertEqual(len(totals),3)
  self.assertEqual(len(ml),1)
  t=totals_table_for_line(totals,6.5,{'over':.57,'under':.43,'push':0})
  self.assertEqual(len(t),2)
  self.assertAlmostEqual(consensus_for_line(t,6.5),.5)
  self.assertNotIn('Underdog',[x['provider'] for x in t])
 def test_provider_names_present(self):
  names=' '.join(name for name,_ in PROVIDERS.values()).lower()
  for p in ['hard rock','fanduel','draftkings','betmgm','caesars','kalshi','underdog','prizepicks','fanatics']:
   self.assertIn(p,names)
 def test_stale_not_value(self):
  total,_=normalize_event_markets(self.payload[0],now=ST+timedelta(minutes=45))
  t=totals_table_for_line(total,6.5,{'over':.57,'under':.43,'push':0})
  self.assertTrue(all(x['model_over_roi_reference'] is None for x in t))
 def test_redacts_api_key_in_error(self):
  from urllib.error import HTTPError
  def error(url):
   raise HTTPError(url,401,'Unauthorized',None,None)
  with self.assertRaises(RuntimeError) as ctx:fetch_book_odds('SUPER_SECRET_TEST_KEY',opener=error)
  self.assertNotIn('SUPER_SECRET_TEST_KEY',str(ctx.exception))
 def test_dfs_props_separate(self):
  p={'bookmakers':[{'key':'underdog','markets':[{'key':'pitcher_strikeouts','outcomes':[{'name':'Over','description':'Drew Rasmussen','point':5.5,'price':1.5}]}]}]}
  rows=normalize_dfs_props(p)
  self.assertEqual(rows[0]['Line'],5.5)
  self.assertIn('NOT game',rows[0]['Caution'])
 def test_odds_fetch_url_is_provider_sourced(self):
  def fake(url):return self.payload
  self.assertEqual(fetch_book_odds('key',opener=fake),self.payload)
  self.assertEqual(fetch_dfs_props('key','event123456',opener=fake),self.payload)

class QuoteLogTests(unittest.TestCase):
 def test_pregame_only_and_audit_stamp(self):
  import tempfile
  from pathlib import Path
  match={'id':'123456','away':'LAN','home':'MIL','start_utc':ST.isoformat()}
  with tempfile.TemporaryDirectory() as td:
   dest=Path(td)/'quotes.jsonl'
   record=record_manual_quote(match,'Kalshi','Over',6.5,45,'kalshi_yes_ask_cents',.51,dest,fees=1,now=ST-timedelta(minutes=10))
   self.assertTrue(dest.exists())
   self.assertFalse(record['trade_executed'])
   self.assertIn('sha256',record)
   with self.assertRaises(ValueError):
    record_manual_quote(match,'Kalshi','Over',6.5,45,'kalshi_yes_ask_cents',.51,dest,now=ST)
   self.assertEqual(len(dest.read_text().splitlines()),1)
 def test_quote_types_and_checks(self):
  import tempfile
  from pathlib import Path
  match={'id':'123456','away':'LAN','home':'MIL','start_utc':ST.isoformat()}
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'x.jsonl'
   record_manual_quote(match,'Hard Rock Bet FL','Under',7.5,1.91,'decimal',.55,d,now=ST-timedelta(minutes=5))
   with self.assertRaises(ValueError):
    record_manual_quote(match,'Kalshi','Under',7.5,99,'kalshi_yes_ask_cents',.55,d,fees=2,now=ST-timedelta(minutes=5))

class ReadinessTests(unittest.TestCase):
 def test_weather_direction(self):
  x={'weather':{'temp':'82','wind':'12 mph, Out To CF'}}
  w=parse_mlb_weather(x)
  self.assertEqual((w['temp'],w['wind_mph'],w['direction']),(82.,12.,'out'))
  self.assertIsNone(parse_mlb_weather({'weather':{'wind':'12 mph, W'}})['wind_mph'])
 def test_before_pitch_gate(self):
  m={'id':'123456','start_utc':ST.isoformat()}
  self.assertTrue(is_verified_pregame(m,ST-timedelta(seconds=1)))
  self.assertFalse(is_verified_pregame(m,ST))
  self.assertFalse(is_verified_pregame({'id':'fake','start_utc':ST.isoformat()},ST-timedelta(hours=1)))

if __name__=='__main__':unittest.main()
