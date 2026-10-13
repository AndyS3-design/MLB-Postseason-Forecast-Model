"""Read-only MLB market research via The Odds API V4 plus manual verified quotes.

- Each bookmaker/source remains distinctly labeled. No fabricated prices.
- DFS player props, exchanges and sportsbooks are not interchangeable.
- Historical/indicative quote != executable offer.
- Never uses prices to alter model probabilities; it only compares them.
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from v5_totals import american_to_decimal, expected_unit_roi, normalized_market_probs

API='https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/'
EVENT_API='https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds/'
PROVIDERS={
 'hardrockbet_fl':('Hard Rock Bet (FL)','Florida licensed sportsbook'),
 'hardrockbet':('Hard Rock Bet (other state)','Reference sportsbook'),
 'draftkings':('DraftKings','Out-of-state reference sportsbook'),
 'fanduel':('FanDuel','Out-of-state reference sportsbook'),
 'betmgm':('BetMGM','Out-of-state reference sportsbook'),
 'williamhill_us':('Caesars','Out-of-state reference sportsbook'),
 'fanatics':('Fanatics','Out-of-state reference sportsbook'),
 'espnbet':('theScore Bet (formerly ESPN BET)','Out-of-state reference sportsbook'),
 'betrivers':('BetRivers','Out-of-state reference sportsbook'),
 'kalshi':('Kalshi','Exchange; indicative feed only, check executable YES ask and fees'),
 'underdog':('Underdog','Fantasy/prediction picks; products and settlement vary'),
 'prizepicks':('PrizePicks','Fantasy/player picks and event contracts; verify market terms'),
}
SPORTSBOOKS=set(PROVIDERS)-{'kalshi','underdog','prizepicks'}
DFS={'underdog','prizepicks'}
EXCHANGES={'kalshi'}


def normalize_team(name):
    """Conservative full-name matching; don't match 'Los Angeles' alone."""
    s=re.sub(r'[^a-z0-9]+','',str(name).lower())
    aliases={'tampabayrays':'tampabayrays', 'tbrays':'tampabayrays',
             'oaklandathletics':'athletics','athletics':'athletics',
             'clevelandindians':'clevelandguardians'}
    return aliases.get(s,s)


def _timestamp(value):
    try:
        t=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError):
        return None


def _request(url,key,params,timeout=15,opener=None):
    if not key or not key.strip():raise ValueError('Odds API key not provided')
    params={**params,'apiKey':key.strip()}
    full=url+'?'+urlencode(params)
    try:
        if opener:
            return opener(full)
        req=Request(full,headers={'User-Agent':'MLB Prediction Lab V5 research / 1.0'})
        with urlopen(req,timeout=timeout) as conn:
            return json.load(conn)
    except HTTPError as exc:
        # Do NOT expose URLs that contain the user's API key.
        raise RuntimeError(f'Odds data provider returned HTTP {exc.code}; check plan/quota, key and market availability') from None
    except (URLError,TimeoutError):
        raise RuntimeError('Odds data provider unavailable or connection timed out') from None


def fetch_book_odds(key,opener=None):
    """Costs API quota: h2h + totals over three regions: us, us2, us_ex."""
    return _request(API,key,{'regions':'us,us2,us_ex','markets':'h2h,totals','oddsFormat':'decimal'},opener=opener)


def find_event(payload,away,home,start_utc=None):
    if not isinstance(payload,list):raise ValueError('Unexpected odds feed payload')
    candidates=[]
    a,h=normalize_team(away),normalize_team(home)
    start=_timestamp(start_utc) if start_utc else None
    for event in payload:
        if normalize_team(event.get('away_team'))!=a or normalize_team(event.get('home_team'))!=h:continue
        stamp=_timestamp(event.get('commence_time'))
        if start and (not stamp or abs((stamp-start).total_seconds())>3*3600):continue
        gap=abs((stamp-start).total_seconds()) if start and stamp else 0
        candidates.append((gap,event))
    return sorted(candidates,key=lambda x:x[0])[0][1] if candidates else None


def _extract_totals(book):
    out=[]
    for m in book.get('markets') or []:
        if m.get('key')!='totals':continue
        by_line={}
        for entry in m.get('outcomes') or []:
            try:
                pt=float(entry['point']);price=float(entry['price'])
            except (KeyError,ValueError,TypeError):continue
            if price<=1 or not 0<=pt<=30:continue
            direction=str(entry.get('name','')).strip().lower()
            if direction not in ('over','under'):continue
            by_line.setdefault(pt,{})[direction]=price
        for pt,prices in by_line.items():
            out.append({'line':pt,'over_decimal':prices.get('over'),'under_decimal':prices.get('under')})
    return out


def _extract_moneylines(book,home,away):
    for m in book.get('markets') or []:
        if m.get('key')!='h2h':continue
        found={}
        for val in m.get('outcomes') or []:
            try:price=float(val['price'])
            except (KeyError,ValueError,TypeError):continue
            if price<=1:continue
            name=normalize_team(val.get('name'))
            if name==normalize_team(home):found['home_decimal']=price
            if name==normalize_team(away):found['away_decimal']=price
        if found:return found
    return {}


def _fmt_market_row(book,market,now):
    name,description=PROVIDERS[book['key']]
    updated=_timestamp(market.get('last_update') or book.get('last_update'))
    age=(now-updated).total_seconds()/60 if updated else None
    # No executable quote claim even if fresh: aggregator may lag.
    status=('Recent reference' if age is not None and -2<=age<=10 else 'Stale/unknown timestamp')
    return dict(provider=name,provider_key=book['key'],type=description,quote_status=status,
                updated_utc=updated.isoformat() if updated else 'Not provided',age_min=round(age,1) if age is not None else None)


def normalize_event_markets(event,now=None):
    """Use only exact published lines; never interpolate across different totals."""
    if not event:return [],[]
    now=now or datetime.now(timezone.utc)
    all_totals=[];winners=[]
    for b in event.get('bookmakers') or []:
        key=str(b.get('key','')).lower()
        if key not in PROVIDERS:continue
        meta=_fmt_market_row(b,{},now)
        # For player-pick sites, do not imply that player props price game totals.
        if key in DFS:continue
        for line in _extract_totals(b):
            all_totals.append({**meta,**line,'kind':'game total',
                'comparable':key in SPORTSBOOKS,'indicative_only':True})
        ml=_extract_moneylines(b,event['home_team'],event['away_team'])
        if ml:winners.append({**meta,**ml,'kind':'game winner','indicative_only':True})
    return all_totals,winners


def totals_table_for_line(rows,line,model_probabilities,staleness_filter=True):
    """Only evaluate books posting the exact selected number; no synthetic repricing.
    Rows without both sides are shown but cannot form no-vig consensus.
    """
    desired=float(line);table=[]
    for r in rows:
        if abs(float(r['line'])-desired)>1e-7:continue
        x=dict(r)
        o=x.get('over_decimal');u=x.get('under_decimal')
        if o and u and desired%1!=0 and r.get('comparable'):
            x['market_no_vig_over']=normalized_market_probs(o,u)['over']
        else:x['market_no_vig_over']=None
        if staleness_filter and x['quote_status']!='Recent reference':
            x['model_over_roi_reference']=None
        elif o and x.get('comparable'):
            x['model_over_roi_reference']=expected_unit_roi(model_probabilities['over'],model_probabilities['push'],o)
        else:x['model_over_roi_reference']=None
        table.append(x)
    return table


def consensus_for_line(rows,line,minimum=2):
    """Median no-vig OVER for >=2 independently priced sportsbook markets.
    Reference only, not a model input, excludes exchanges and DFS.
    """
    import statistics
    vals=[r['market_no_vig_over'] for r in rows if float(r['line'])==float(line)
          and r.get('market_no_vig_over') is not None and r.get('quote_status')=='Recent reference']
    return float(statistics.median(vals)) if len(vals)>=minimum else None


def fetch_dfs_props(key,event_id,opener=None):
    if not event_id or not re.fullmatch(r'[a-zA-Z0-9_-]{6,120}',str(event_id)):
        raise ValueError('Valid provider event id required')
    return _request(EVENT_API.format(event_id=event_id),key,
        {'regions':'us_dfs','markets':'pitcher_strikeouts,batter_hits','oddsFormat':'decimal'},opener=opener)


def normalize_dfs_props(event):
    items=[]
    for book in event.get('bookmakers') or []:
        k=str(book.get('key','')).lower()
        if k not in DFS:continue
        for m in book.get('markets') or []:
            for outcome in m.get('outcomes') or []:
                point=outcome.get('point')
                if point is None:continue
                items.append({'Platform':PROVIDERS[k][0],'Player':outcome.get('description',''),
                    'Prop':m.get('key',''),'Direction':outcome.get('name',''),
                    'Line':point,'Indicative price':outcome.get('price'),
                    'Updated UTC':m.get('last_update') or book.get('last_update',''),
                    'Caution':'DFS multiplier/contest payoff may differ; NOT game O/U odds'})
    return items
