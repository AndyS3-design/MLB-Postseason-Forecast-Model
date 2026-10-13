#!/usr/bin/env python3
"""Sportsbook odds calibration, NOT tradable Kalshi order evaluation.
Requires time-stamped pregame home/away American moneylines for identical games.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from backtest import metrics


def implied(american):
    x=float(american)
    if x==0 or (x>-100 and x<100):raise ValueError(f'Invalid American odds: {x}')
    return (-x)/(-x+100) if x<0 else 100/(100+x)


def evaluate(p,odds):
    for name in ('game_id','quote_timestamp_utc','first_pitch_utc','home_american','away_american'):
        if name not in odds:raise ValueError('Missing sportsbook column: '+name)
    q=odds.copy();q['game_id']=q.game_id.astype(str)
    q['quote_timestamp_utc']=pd.to_datetime(q.quote_timestamp_utc,utc=True)
    q['first_pitch_utc']=pd.to_datetime(q.first_pitch_utc,utc=True)
    if (q.quote_timestamp_utc>=q.first_pitch_utc).any():raise ValueError('Odds not strictly before game')
    q=q.sort_values('quote_timestamp_utc').drop_duplicates('game_id',keep='last')
    q['raw_home']=q.home_american.map(implied);q['raw_away']=q.away_american.map(implied)
    q['vig']=q.raw_home+q.raw_away-1
    if (q.vig<-.015).any() or (q.vig>.3).any():raise ValueError('Implausible market vig or wrong odds')
    q['no_vig_home']=q.raw_home/(q.raw_home+q.raw_away)
    df=q.merge(p[['game_id','actual_home_win','p_home_elo']],on='game_id',how='inner',validate='one_to_one')
    if not len(df):return {'status':'no_matching_games','n':0}
    out={'status':'verified_sportsbook_comparison','n':len(df),'mean_vig':float(df.vig.mean()),
         'sportsbook_no_vig':metrics(df.actual_home_win,df.no_vig_home),
         'elo':metrics(df.actual_home_win,df.p_home_elo)}
    out['warning']='These are pregame bookmaker quotes, not Kalshi executable asks. NO Kalshi profitability inferred.'
    return out


def main():
    x=argparse.ArgumentParser()
    x.add_argument('--predictions',type=Path,default=Path(__file__).parent/'outputs'/'extended_predictions.csv')
    x.add_argument('--odds',type=Path,default=Path(__file__).parent/'data'/'historical_sportsbook_odds.csv')
    x.add_argument('--out-dir',type=Path,default=Path(__file__).parent/'outputs')
    a=x.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
    if not a.odds.exists():result={'status':'unavailable','reason':'No historical sportsbook moneylines supplied; no market-calibration comparison run.'}
    else:result=evaluate(pd.read_csv(a.predictions,dtype={'game_id':str}),pd.read_csv(a.odds,dtype={'game_id':str}))
    (a.out_dir/'sportsbook_comparison.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
