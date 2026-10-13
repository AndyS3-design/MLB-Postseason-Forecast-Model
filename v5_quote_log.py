"""Append-only, locally recorded user observations; never auto-executed bets."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json,math
from v5_pregame import is_verified_pregame


def record_manual_quote(match,provider,market_side,line,price,price_type,model_p,output,fees=0.0,now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or not is_verified_pregame(match,now):
        raise ValueError('New pregame quote observations are blocked after scheduled first pitch or for unverified games')
    if provider is None or not str(provider).strip():raise ValueError('Provider required')
    if market_side not in ('Over','Under'):raise ValueError('Market direction required')
    for value in (line,price,fees,model_p):
        if not math.isfinite(float(value)):raise ValueError('Finite numeric quote inputs required')
    if not .5<=float(line)<=40.5 or float(fees)<0 or not 0<=float(model_p)<=1:
        raise ValueError('Invalid total line, fee or model probability')
    if price_type=='decimal' and float(price)<=1:raise ValueError('Decimal price must exceed 1')
    if price_type=='kalshi_yes_ask_cents' and not 0<float(price)<100-float(fees):
        raise ValueError('Kalshi YES ask plus fees must be less than 100 cents')
    if price_type not in ('decimal','kalshi_yes_ask_cents'):
        raise ValueError('Unsupported quote price format')
    record={'captured_utc':now.isoformat(),'scheduled_start_utc':str(match['start_utc']),
       'game_id':str(match['id']),'away':str(match['away']),'home':str(match['home']),
       'provider':str(provider),'market':'full_game_total','line':float(line),
       'direction':market_side,'price_type':price_type,'price':float(price),
       'estimated_fees':float(fees),'model_probability':float(model_p),
       'source':'MANUALLY ENTERED; USER MUST VERIFY EXECUTABLE PRICE',
       'trade_executed':False,'market_terms_verified':False}
    record['sha256']=sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('a',encoding='utf-8') as f:f.write(json.dumps(record,sort_keys=True)+'\n')
    return record
