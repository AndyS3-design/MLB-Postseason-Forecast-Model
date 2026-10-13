#!/usr/bin/env python3
"""Pricing/ROI evaluation from historical, timestamped, *executable* YES asks.

This is deliberately NOT a synthetic odds generator. With no real quotes,
it produces an unavailable-data report, not a profitability estimate.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

MARKETS={'home_win':'p_home_elo','away_win':'p_home_elo','under_6_5':'p_under_6_5_run_model',
         'over_6_5':'p_under_6_5_run_model'}
TRUTH={'home_win':'actual_home_win','away_win':'actual_home_win','under_6_5':'actual_under_6_5',
       'over_6_5':'actual_under_6_5'}
REQUIRED=['game_id','market','price_source','is_executable','quote_timestamp_utc',
          'first_pitch_utc','yes_ask','fee_per_contract_usd']


def true_bool(s):
    if isinstance(s,bool):return s
    if str(s).strip().lower() in ('true','1','yes'):return True
    if str(s).strip().lower() in ('false','0','no'):return False
    raise ValueError(f'Invalid executable flag: {s}')


def analyze(predictions,quotes,edge_threshold=.05,max_quote_age_hours=6):
    if not len(quotes):return {'status':'no_quotes','n_quotes':0,'n_trades':0},pd.DataFrame()
    miss=set(REQUIRED)-set(quotes.columns)
    if miss:raise ValueError(f'Missing quote columns: {sorted(miss)}')
    q=quotes.copy()
    if q[REQUIRED].isna().any().any():raise ValueError('Missing required values in market quote data')
    q['is_executable']=q.is_executable.map(true_bool)
    q['quote_timestamp_utc']=pd.to_datetime(q.quote_timestamp_utc,utc=True,errors='raise')
    q['first_pitch_utc']=pd.to_datetime(q.first_pitch_utc,utc=True,errors='raise')
    q['yes_ask']=pd.to_numeric(q.yes_ask,errors='raise')
    q['fee_per_contract_usd']=pd.to_numeric(q.fee_per_contract_usd,errors='raise')
    if (~q.market.isin(MARKETS)).any():raise ValueError('Unsupported market '+str(q.loc[~q.market.isin(MARKETS),'market'].unique()))
    if (~q.yes_ask.between(0.001,.999)).any():raise ValueError('YES ask must be price per $1 payout (0,1)')
    if (q.fee_per_contract_usd<0).any():raise ValueError('Fees must be nonnegative')
    if (q.yes_ask+q.fee_per_contract_usd>=1).any():raise ValueError('Ask+fee must be less than payout')
    # Historical markets must NOT have a price observed during or after the game.
    if (q.quote_timestamp_utc>=q.first_pitch_utc).any():
        raise ValueError('Quote timestamp at/after first pitch: potential lookahead bias')
    age=(q.first_pitch_utc-q.quote_timestamp_utc).dt.total_seconds()/3600
    if (age>max_quote_age_hours).any():
        raise ValueError('Stale quote older than max_quote_age_hours: not credible at game time')
    if not q.is_executable.all():
        raise ValueError('Non-executable indicative quote(s); cannot backtest fills or ROI')
    # Uniqueness: use uniquely identified scheduled game to avoid doubleheader confusion.
    q=q.sort_values('quote_timestamp_utc').drop_duplicates(['game_id','market'],keep='last')
    if predictions.game_id.duplicated().any():raise ValueError('Repeated game predictions')
    p=predictions.copy();p['game_id']=p.game_id.astype(str);q['game_id']=q.game_id.astype(str)
    merged=q.merge(p,on='game_id',how='left',validate='many_to_one',indicator=True)
    if (merged['_merge']!='both').any():raise ValueError('Quote does not match a predicted game ID; never fuzzy-match odds')
    probs=[];ys=[]
    for _,r in merged.iterrows():
        col=MARKETS[r['market']];target=TRUTH[r['market']]
        prob=r.get(col)
        if pd.isna(prob):raise ValueError('No tested model probability for '+r['market'])
        y=int(r[target]);
        if r['market'] in ('away_win','over_6_5'):
            prob=1-float(prob);y=1-y
        probs.append(float(prob));ys.append(y)
    merged['model_yes_p']=probs;merged['actual_yes']=ys
    merged['implied_yes_p_after_fee']=merged.yes_ask+merged.fee_per_contract_usd
    merged['estimated_ev_usd_per_contract']=merged.model_yes_p-merged.implied_yes_p_after_fee
    merged['modeled_edge_pp']=100*merged.estimated_ev_usd_per_contract
    eligible=merged[merged.estimated_ev_usd_per_contract>=edge_threshold].copy()
    # One trade per game; do not count correlated contracts as independent bets.
    eligible=eligible.sort_values(['game_id','estimated_ev_usd_per_contract'],ascending=[True,False]).drop_duplicates('game_id')
    if len(eligible):
        eligible['realized_pnl_usd']=eligible.actual_yes.astype(float)-eligible.yes_ask-eligible.fee_per_contract_usd
        eligible['amount_spent_usd']=eligible.yes_ask+eligible.fee_per_contract_usd
        eligible=eligible.sort_values(['first_pitch_utc','game_id'])
        total_profit=float(eligible.realized_pnl_usd.sum())
        total_spend=float(eligible.amount_spent_usd.sum())
        hit=float(eligible.actual_yes.mean())
        maxdraw=float((eligible.realized_pnl_usd.cumsum()-eligible.realized_pnl_usd.cumsum().cummax().clip(lower=0)).min())
        stat={'status':'completed_with_quoted_prices','n_quotes':len(merged),'n_trades':len(eligible),
              'minimum_estimated_edge_pp':edge_threshold*100,
              'wins':int(eligible.actual_yes.sum()),'hit_rate':hit,
              'total_staked_usd':total_spend,'net_pnl_usd':total_profit,
              'roi_on_contract_spend':total_profit/total_spend,'max_running_drawdown_usd':maxdraw}
    else:
        stat={'status':'completed_no_trades','n_quotes':len(merged),'n_trades':0,
              'minimum_estimated_edge_pp':edge_threshold*100}
    return stat,eligible


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--predictions',type=Path,default=Path(__file__).parent/'outputs'/'extended_predictions.csv')
    p.add_argument('--quotes',type=Path,default=Path(__file__).parent/'data'/'historical_kalshi_quotes.csv')
    p.add_argument('--out-dir',type=Path,default=Path(__file__).parent/'outputs')
    p.add_argument('--edge-threshold',type=float,default=.05)
    args=p.parse_args();args.out_dir.mkdir(parents=True,exist_ok=True)
    if not args.quotes.exists():
        output={'status':'unavailable','n_quotes':0,'n_trades':0,
                'reason':'No timestamped historical executable YES asks + fees were supplied. Odds cannot be inferred from game results.',
                'note':'Sportsbook opening/closing lines are not Kalshi fillable quotes; record those separately as market calibration baselines.'}
    else:
        preds=pd.read_csv(args.predictions,dtype={'game_id':str})
        quotes=pd.read_csv(args.quotes,dtype={'game_id':str})
        output,trades=analyze(preds,quotes,args.edge_threshold)
        if len(trades):trades.to_csv(args.out_dir/'verified_market_trades.csv',index=False)
    (args.out_dir/'market_backtest.json').write_text(json.dumps(output,indent=2))
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
