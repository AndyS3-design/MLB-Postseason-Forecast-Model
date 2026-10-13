"""Totals-first model calculations. A model probability is NOT a proven betting edge."""
from __future__ import annotations
import math


def _valid_pmf(pmf):
    if not pmf:
        raise ValueError('No simulated total-run probability distribution available')
    values={int(k):float(v) for k,v in pmf.items()}
    if any(k<0 or not math.isfinite(v) or v<0 for k,v in values.items()):
        raise ValueError('Invalid scoring distribution')
    if abs(sum(values.values())-1)>1e-6:
        raise ValueError('Total-run distribution not normalized')
    return values


def probabilities_for_line(pmf,line):
    """For integer lines model the push separately; half-runs cannot push."""
    dist=_valid_pmf(pmf)
    line=float(line)
    if not math.isfinite(line) or line<0 or line>40:
        raise ValueError('Invalid total line')
    over=sum(p for runs,p in dist.items() if runs>line)
    under=sum(p for runs,p in dist.items() if runs<line)
    push=sum(p for runs,p in dist.items() if runs==line)
    return {'over':over,'under':under,'push':push,'line':line}


def representative_score(forecast):
    """Pick ONE most frequent exact score consistent with simulated favorite."""
    h_wins=float(forecast['home_win_probability'])>=.5
    preferred=forecast.get('representative_score')
    if preferred:
        return preferred
    scores=forecast.get('modal_exact_scores',[])
    options=[s for s in scores if (int(s['home'])>int(s['away']))==h_wins]
    if not options:
        options=scores
    if not options:
        raise ValueError('No modal score distribution')
    return max(options,key=lambda s:s['probability'])


def fair_decimal(p, push=0.0):
    """Break-even decimal odds assuming pushes refund stake."""
    if not 0<p<=1 or not 0<=push<1 or p+push>1+1e-6:
        return None
    return (1-push)/p


def expected_unit_roi(p_win,p_push,decimal_price):
    p_win=float(p_win);p_push=float(p_push);price=float(decimal_price)
    if not (0<=p_win<=1 and 0<=p_push<=1 and p_win+p_push<=1.000001 and price>1 and math.isfinite(price)):
        raise ValueError('Invalid probabilities or decimal odds')
    return p_win*(price-1)-(1-p_win-p_push)


def american_to_decimal(american):
    odds=float(american)
    if not math.isfinite(odds) or abs(odds)<100:
        raise ValueError('American odds should be at least +/-100')
    return 1+odds/100 if odds>0 else 1+100/abs(odds)


def decimal_to_american(decimal):
    price=float(decimal)
    if price<=1 or not math.isfinite(price):raise ValueError('Decimal odds must exceed 1')
    return round((price-1)*100) if price>=2 else round(-100/(price-1))


def kalshi_contract_edge(model_probability,ask_cents,fees_cents=0):
    """Only for a verified single YES contract paying $1, excluding slippage."""
    p=float(model_probability);cost=float(ask_cents);fees=float(fees_cents)
    if not 0<=p<=1 or not (0<cost<100) or fees<0 or cost+fees>=100:
        raise ValueError('Invalid contract price/fees')
    return {'break_even':(cost+fees)/100,'expected_dollars_per_contract':p-(cost+fees)/100,
        'probability_minus_break_even_pp':100*(p-(cost+fees)/100)}


def normalized_market_probs(over_decimal,under_decimal):
    """For matching half-run lines, removal of vig by proportional normalization."""
    o=float(over_decimal);u=float(under_decimal)
    if min(o,u)<=1:raise ValueError('Prices must be decimal odds above 1')
    raw_o,raw_u=1/o,1/u
    return {'over':raw_o/(raw_o+raw_u),'under':raw_u/(raw_o+raw_u),'overround':raw_o+raw_u}
