#!/usr/bin/env python3
"""Append-only *local research* MLB pregame forecast/quote/paper-trade tracker.

All evidence used for a forecast has a game-date cutoff STRICTLY before its date.
Real UTC snapshot time must precede the verified official MLB scheduled first pitch.
No Kalshi account access, no trade execution, and no automatic quote retrieval.

Run: py prospective_tracker.py list --date 2026-10-12
     py prospective_tracker.py freeze --date 2026-10-12 --game-id <MLB gamePk>
     py prospective_tracker.py watch --date 2026-10-12 --lead-minutes 60
     py prospective_tracker.py quote --game-id <gamePk> --market home_win --ask-cents 55 --fee-cents 2 --attest
     py prospective_tracker.py paper --quote-id <quote_id>
     py prospective_tracker.py settle --date 2026-10-12
     py prospective_tracker.py report
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import uuid
import zlib
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

ROOT=Path(__file__).resolve().parent
STORE=ROOT/'outputs'/'prospective'
SOURCE_FILES=('forecast_engine.py','score_projection.py','backtest.py','extended_eval.py',
              'matchup_model.py','robust_score_validation.py')
DATA_FILES=('GL2023.TXT','GL2024.TXT','GL2025.TXT','mlb_2026_regular.csv',
            'mlb_postseason_2023_2026.csv','advanced_pitching_details.csv','pitcher_directory.csv')
MODELS=('poisson','validated_nb','wide_nb','constant_nb')
MARKETS=('home_win','away_win','under_6_5','over_6_5')


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(x):
    if isinstance(x,datetime): d=x
    else: d=datetime.fromisoformat(str(x).replace('Z','+00:00'))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError('UTC-aware MLB kickoff and capture timestamps are required')
    return d.astimezone(timezone.utc)


def timestamp(d):
    return parse_time(d).isoformat().replace('+00:00','Z')


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def fingerprint(root=ROOT):
    """A fingerprint of model and DATA FILES frozen at the instant of logging."""
    root=Path(root);digest=hashlib.sha256()
    for name in SOURCE_FILES:
        f=root/name
        if not f.exists():raise FileNotFoundError(f'Model source missing: {f}')
        digest.update(name.encode());digest.update(hashlib.sha256(f.read_bytes()).digest())
    return digest.hexdigest()


def data_fingerprint(data_dir):
    data_dir=Path(data_dir);digest=hashlib.sha256()
    for name in DATA_FILES:
        f=data_dir/name
        digest.update(name.encode())
        digest.update(hashlib.sha256(f.read_bytes()).digest() if f.exists() else b'MISSING')
    return digest.hexdigest()


def read_log(path):
    """Verify a chain of locally stored JSONL records. Tamper EVIDENT, not tamper proof."""
    path=Path(path)
    if not path.exists():return []
    prev='0'*64;out=[]
    for lineno,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        try: obj=json.loads(line)
        except ValueError as exc:raise ValueError(f'Corrupt {path.name} line {lineno}') from exc
        expected=obj.get('record_hash');without={k:v for k,v in obj.items() if k!='record_hash'}
        if without.get('prev_hash')!=prev or hashlib.sha256(canonical(without).encode()).hexdigest()!=expected:
            raise ValueError(f'{path.name} audit chain is inconsistent on line {lineno}; do not use it for results')
        out.append(obj);prev=expected
    return out


def append_record(path,payload):
    """Single-user append-only local audit. Don't write from two processes at once."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    old=read_log(path)
    item=dict(payload)
    item['prev_hash']=old[-1]['record_hash'] if old else '0'*64
    item['record_hash']=hashlib.sha256(canonical(item).encode()).hexdigest()
    blob=(canonical(item)+'\n').encode('utf-8')
    flags=os.O_WRONLY|os.O_APPEND|os.O_CREAT
    fd=os.open(path,flags,0o600)
    try:
        if os.write(fd,blob)!=len(blob):raise OSError('Short write to the local journal')
        os.fsync(fd)
    finally:os.close(fd)
    return item


def paths(store=STORE):
    s=Path(store)
    return {n:s/f'{n}.jsonl' for n in ('forecasts','quotes','paper_entries','results')}


def normal_id(game_id):
    s=str(game_id).removeprefix('api-')
    if not s.isdecimal() or int(s)<=0:raise ValueError('An official MLB gamePk is required')
    return s


def require_pregame(match,now=None):
    """Fail closed: this check is repeated on every save. Not a live-play model."""
    now=parse_time(now or utc_now())
    kickoff=parse_time(match['start_utc'])
    status=str(match.get('status','')).casefold().strip()
    if any(bad in status for bad in ('in progress','final','game over','completed','suspended','postponed','cancelled','canceled')):
        raise ValueError(f'Official MLB status is {match.get("status")!r}, not pregame')
    if now>=kickoff:
        raise ValueError('Scheduled first pitch has passed: cannot create a retrospective "pregame" record.')
    if (kickoff-now).total_seconds()>24*60*60:
        raise ValueError('Premature snapshot (>24h before first pitch); log nearer the game for a credible quote comparison.')
    if not status or status=='unknown':
        raise ValueError('Unverified MLB game status; cannot certify pregame.')
    if str(match.get('id',''))=='':raise ValueError('Official MLB game ID required')
    return now,kickoff


def find_official_game(game_id,game_date,fetcher=None):
    from forecast_engine import fetch_schedule
    fetcher=fetcher or fetch_schedule
    matches=[m for m in fetcher(game_date) if normal_id(m['id'])==normal_id(game_id)]
    if len(matches)!=1:raise ValueError('Game is missing/duplicated in freshly fetched official MLB schedule')
    return matches[0]


def compress_matrix(mat):
    a=np.asarray(mat,dtype=np.float64)
    if a.ndim!=2 or a.shape[0]!=a.shape[1] or not np.isclose(a.sum(),1,atol=1e-7):
        raise ValueError('Invalid probability matrix')
    return {'shape':list(a.shape),'dtype':'float64','codec':'zlib+base64',
            'values':base64.b64encode(zlib.compress(a.tobytes(),level=8)).decode('ascii')}


def decompress_matrix(item):
    raw=zlib.decompress(base64.b64decode(item['values'],validate=True))
    shape=tuple(item['shape'])
    if len(shape)!=2 or shape[0]!=shape[1] or not 10<=shape[0]<=100:raise ValueError('Bad saved matrix shape')
    if item.get('codec')!='zlib+base64' or item.get('dtype')!='float64':raise ValueError('Bad saved matrix codec')
    a=np.frombuffer(raw,dtype=np.float64).reshape(shape)
    if np.any(a<0) or not np.isclose(a.sum(),1,atol=1e-7):raise ValueError('Corrupt score distribution')
    return a


def forecast_snapshot(match,games,run_fit,now=None,root=ROOT,expanded=None):
    """The only allowed pregame forecast creation path, with strict timing."""
    from forecast_engine import forecast
    from robust_score_validation import score_candidate,discrete_interval
    from score_projection import summarize_score_matrix
    from backtest import read_rows
    from datetime import date as date_type

    stamp,kick=require_pregame(match,now)
    day=date_type.fromisoformat(match['date'])
    if parse_time(match['start_utc']).date() not in (day,day+__import__('datetime').timedelta(days=1)):
        raise ValueError('Game date and MLB start timestamp are inconsistent')
    if run_fit is None:raise ValueError('The 2023-24 frozen scoring fit is required for prospective logging')
    model,feature_names,ah,aa,extras=run_fit
    forecast_value=forecast(games,day,match['home'],match['away'],run_fit)
    # Fixed, historically estimated baseline, no games in the target season.
    training=read_rows(Path(root)/'data')
    baseh=float(np.mean([g['home_reg'] for g in training if g['year'] in (2023,2024)]))
    basea=float(np.mean([g['away_reg'] for g in training if g['year'] in (2023,2024)]))
    distributions={};summaries={}
    for name in MODELS:
        mat=score_candidate(forecast_value['home_runs_regulation'],forecast_value['away_runs_regulation'],
                            ah,aa,extras,forecast_value['home_win_probability'],name,baseh,basea)
        distributions[name]=compress_matrix(mat)
        desc=summarize_score_matrix(mat)
        h,a=np.indices(mat.shape)
        totals=np.bincount((h+a).ravel(),weights=mat.ravel(),minlength=2*mat.shape[0]-1)
        summaries[name]={'under_6_5_probability':float(mat[h+a<=6].sum()),
                         'representative_favorite_score':desc['representative_favorite_score'],
                         'expected_home_runs':desc['expected_home_final'],
                         'expected_away_runs':desc['expected_away_final'],
                         'total_80pct_interval':list(discrete_interval(totals,.8)),
                         'total_90pct_interval':list(discrete_interval(totals,.9))}
    result={'schema_version':1,'record_type':'frozen_pregame_forecast',
        'forecast_id':uuid.uuid4().hex,'created_at_utc':timestamp(stamp),
        'first_pitch_utc':timestamp(kick),'model_code_sha256':fingerprint(root),
        'historical_data_sha256':data_fingerprint(Path(root)/'data'),
        'game_id':normal_id(match['id']),'game_date':day.isoformat(),
        'matchup':{'home':match['home'],'away':match['away'],
                   'home_name':match.get('home_name',match['home']),
                   'away_name':match.get('away_name',match['away']),
                   'home_pitcher':match.get('home_pitcher'),
                   'away_pitcher':match.get('away_pitcher'),
                   'home_pitcher_id':match.get('home_pitcher_id'),
                   'away_pitcher_id':match.get('away_pitcher_id')},
        'prediction_cutoff_exclusive':day.isoformat(),
        'elo_home_win_probability':forecast_value['home_win_probability'],
        'elo_away_win_probability':forecast_value['away_win_probability'],
        'expanded_research_forecast':expanded,
        'scoring_distributions':distributions,'scoring_summaries':summaries,
        'primary_scoring_variant':'validated_nb',
        'warnings':[
            'Full-game scores are exploratory; model development already examined 2025 and 2026 outcomes.',
            'All score-model winner probabilities are mechanically tilted to Elo.',
            'Postseason-specific adjustments and real-time injuries/lineups are not validated.',
            'Saved quotes are observations and paper trades, not actual Kalshi executions.',
        ]}
    return result


def freeze_game(match,games,run_fit,store=STORE,now=None,root=ROOT,expanded=None,refresh_fetcher=None):
    # Reload official game immediately before saving. Cannot rely on cached UI state.
    fresh=find_official_game(match['id'],date.fromisoformat(match['date']),refresh_fetcher)
    if (fresh['home'],fresh['away'])!=(match['home'],match['away']):
        raise ValueError('Official matchup changed; refresh the page')
    if str(fresh.get('start_utc'))!=str(match.get('start_utc')):
        raise ValueError('Scheduled first pitch changed; refresh before logging')
    existing=read_log(paths(store)['forecasts'])
    if any(r['game_id']==normal_id(match['id']) for r in existing):
        raise ValueError('A frozen forecast already exists for this game; no hindsight re-forecast allowed')
    row=forecast_snapshot(fresh,games,run_fit,now,root,expanded)
    if now is None and utc_now()>=parse_time(row['first_pitch_utc']):
        raise ValueError('First pitch passed while model was computing; forecast NOT saved')
    return append_record(paths(store)['forecasts'],row)


def model_probability(forecast,market):
    if market=='home_win':return float(forecast['elo_home_win_probability'])
    if market=='away_win':return float(forecast['elo_away_win_probability'])
    summaries=forecast['scoring_summaries']['validated_nb']
    if market=='under_6_5':return float(summaries['under_6_5_probability'])
    if market=='over_6_5':return 1-float(summaries['under_6_5_probability'])
    raise ValueError('Unsupported market')


def fresh_pregame_status(forecast,now,refresh_fetcher=None):
    '''Re-fetch official game state at time of quote or paper commitment.'''
    match=find_official_game(forecast['game_id'],date.fromisoformat(forecast['game_date']),refresh_fetcher)
    require_pregame(match,now)
    if (match['home'],match['away'])!=(forecast['matchup']['home'],forecast['matchup']['away']):
        raise ValueError('Official matchup changed; no retrospective price logging')
    if timestamp(match['start_utc'])!=forecast['first_pitch_utc']:
        raise ValueError('Official scheduled start changed; price tracking requires a new verified game record')
    return match


def add_quote(forecast_id,market,ask_cents,fee_cents,attest,store=STORE,now=None,refresh_fetcher=None):
    if not attest:raise ValueError('Attest that the quote came from the LIVE executable BUY-YES order ticket')
    if market not in MARKETS:raise ValueError('Unsupported Kalshi contract market')
    fs=read_log(paths(store)['forecasts']); f=next((x for x in fs if x['forecast_id']==forecast_id),None)
    if f is None:raise ValueError('Choose an already frozen forecast')
    now=parse_time(now or utc_now())
    if now>=parse_time(f['first_pitch_utc']):raise ValueError('Cannot record an actionable pregame quote after scheduled first pitch')
    fresh_pregame_status(f,now,refresh_fetcher)
    try: ask=float(ask_cents);fee=float(fee_cents)
    except (TypeError,ValueError) as exc:raise ValueError('Ask and fee must be numbers') from exc
    if not all(math.isfinite(x) for x in (ask,fee)) or not (0<ask<100 and 0<=fee<100 and ask+fee<100):
        raise ValueError('Ask 0–100 cents; nonnegative per-contract fee; total must be under $1')
    p=model_probability(f,market)
    if now is not None:
        stamped_now=now
    else:
        stamped_now=utc_now()
        if stamped_now>=parse_time(f['first_pitch_utc']):
            raise ValueError('First pitch passed during quote verification; quote NOT saved')
    row={'record_type':'manual_executable_quote_observation','quote_id':uuid.uuid4().hex,
         'forecast_id':forecast_id,'game_id':f['game_id'],'created_at_utc':timestamp(stamped_now),
         'first_pitch_utc':f['first_pitch_utc'],'market':market,
         'yes_ask_cents':ask,'estimated_fee_cents_per_contract':fee,
         'model_yes_probability':p,'implied_break_even_with_fee':(ask+fee)/100,
         'modeled_ev_per_1usd_contract':p-(ask+fee)/100,
         'source':'user-entered Kalshi BUY YES executable quote',
         'is_user_attested':True,'not_a_fill':True}
    return append_record(paths(store)['quotes'],row)


def lock_paper_entry(quote_id,store=STORE,now=None,refresh_fetcher=None):
    q=next((x for x in read_log(paths(store)['quotes']) if x['quote_id']==quote_id),None)
    if q is None:raise ValueError('Unknown quote')
    now=parse_time(now or utc_now())
    if now>=parse_time(q['first_pitch_utc']):raise ValueError('Paper entry cannot be created after first pitch')
    forecast=next((x for x in read_log(paths(store)['forecasts']) if x['forecast_id']==q['forecast_id']),None)
    if forecast is None:raise ValueError('Frozen forecast for quote is missing')
    fresh_pregame_status(forecast,now,refresh_fetcher)
    existing=read_log(paths(store)['paper_entries'])
    if any(x['game_id']==q['game_id'] for x in existing):
        raise ValueError('Only one pre-committed paper position per game for this research sample')
    stamped_now=now if now is not None else utc_now()
    if stamped_now>=parse_time(q['first_pitch_utc']):
        raise ValueError('First pitch passed during status verification; paper entry NOT saved')
    row={'record_type':'hypothetical_paper_position','paper_id':uuid.uuid4().hex,
         'quote_id':quote_id,'game_id':q['game_id'],'forecast_id':q['forecast_id'],
         'created_at_utc':timestamp(stamped_now),'market':q['market'],
         'yes_ask_cents':q['yes_ask_cents'],'estimated_fee_cents_per_contract':q['estimated_fee_cents_per_contract'],
         'contracts':1,'price_was_executable_but_fill_not_verified':True}
    return append_record(paths(store)['paper_entries'],row)


def parse_official_finals(payload,day):
    """Only real official FINAL outcomes; never impute missing scores."""
    out={}
    for block in payload.get('dates',[]):
        for g in block.get('games',[]):
            if str(g.get('officialDate') or block.get('date'))!=day.isoformat():continue
            if g.get('status',{}).get('abstractGameState')!='Final':continue
            try:
                h=g['teams']['home'];a=g['teams']['away']
                hr=int(h['score']);ar=int(a['score'])
                pk=normal_id(g['gamePk'])
                from ingest_mlb import MLB_TO_RETRO
                hc=MLB_TO_RETRO[int(h['team']['id'])];ac=MLB_TO_RETRO[int(a['team']['id'])]
            except (KeyError,ValueError,TypeError):continue
            if hr==ar or hr<0 or ar<0:continue
            out[pk]={'game_id':pk,'game_date':day.isoformat(),
                     'home':hc,'away':ac,'home_final':hr,'away_final':ar}
    return out


def fetch_official_finals(day):
    from ingest_mlb import API
    url=API+'?'+urlencode({'sportId':1,'date':day.isoformat()})
    with urlopen(Request(url,headers={'User-Agent':'Personal MLB research logger'}),timeout=20) as response:
        return parse_official_finals(json.load(response),day)


def settle(day,store=STORE,fetcher=None,now=None):
    now=parse_time(now or utc_now()); day=date.fromisoformat(str(day))
    fetcher=fetcher or fetch_official_finals
    official=fetcher(day)
    forecast_rows=[x for x in read_log(paths(store)['forecasts']) if x['game_date']==day.isoformat()]
    already={x['game_id'] for x in read_log(paths(store)['results'])}
    completed=[]
    for f in forecast_rows:
        gid=f['game_id'];match=official.get(gid)
        if match is None or gid in already:continue
        if (match['home'],match['away'])!=(f['matchup']['home'],f['matchup']['away']):
            raise ValueError('Official team mismatch on result; do not settle by guess')
        if now<parse_time(f['first_pitch_utc']):raise ValueError('Cannot settle before scheduled first pitch')
        row={'record_type':'official_mlb_final','game_id':gid,'forecast_id':f['forecast_id'],
             'settled_at_utc':timestamp(now),'game_date':day.isoformat(),
             'home_final':int(match['home_final']),'away_final':int(match['away_final']),
             'source':'MLB Stats API schedule confirmed Final'}
        completed.append(append_record(paths(store)['results'],row))
    return completed


def bootstrap_diff(values,dates,iterations=1000,seed=17):
    """Paired game-day resampling: mean(model metric - benchmark metric)."""
    if len(values)<30 or len(set(dates))<10:return None
    groups=defaultdict(list)
    for v,d in zip(values,dates):groups[d].append(float(v))
    group_values=[np.array(v,dtype=float) for v in groups.values()]
    rng=np.random.default_rng(seed);n=len(group_values);means=[]
    for _ in range(iterations):
        sampled=rng.integers(0,n,n)
        total=sum(group_values[i].sum() for i in sampled)
        count=sum(len(group_values[i]) for i in sampled)
        means.append(total/count)
    return [float(v) for v in np.quantile(means,[.025,.975])]


def analysis(store=STORE):
    from robust_score_validation import score_metrics
    p=paths(store)
    snapshots=read_log(p['forecasts']);settled={x['game_id']:x for x in read_log(p['results'])}
    quotes=read_log(p['quotes']);paper=read_log(p['paper_entries'])
    rows=[]
    for f in snapshots:
        final=settled.get(f['game_id'])
        if not final:continue
        home=int(final['home_final']);away=int(final['away_final'])
        y=int(home>away)
        row={'game_id':f['game_id'],'game_date':f['game_date'],
             'actual_home_runs':home,'actual_away_runs':away,
             'elo_winner_brier':(f['elo_home_win_probability']-y)**2}
        if f.get('expanded_research_forecast') and 'p_home_expanded' in f['expanded_research_forecast']:
            row['expanded_winner_brier']=(float(f['expanded_research_forecast']['p_home_expanded'])-y)**2
        for name,item in f['scoring_distributions'].items():
            metrics=score_metrics(decompress_matrix(item),home,away)
            for metric,value in metrics.items():row[name+'_'+metric]=value
        rows.append(row)
    result={'status':'completed' if rows else 'no_settled_pregame_games',
            'settled_games':len(rows),'frozen_forecasts':len(snapshots),
            'manual_quote_observations':len(quotes),'precommitted_paper_entries':len(paper),
            'warning':'Research only: timestamped user-entered quotes are not executed fills. Models are not proven profitable.',
            'metrics':{},'paired_intervals':{},'paper_trades':{}}
    if rows:
        for name in MODELS:
            result['metrics'][name]={metric:float(np.mean([x[name+'_'+metric] for x in rows]))
                for metric in ('exact_log_loss','total_crps','under_brier','run_mae','pi80_coverage')}
        result['metrics']['elo']={'winner_brier':float(np.mean([x['elo_winner_brier'] for x in rows]))}
        expanded=[x for x in rows if 'expanded_winner_brier' in x]
        if expanded:
            result['metrics']['expanded']={'winner_brier':float(np.mean([x['expanded_winner_brier'] for x in expanded]))}
            ds=[x['expanded_winner_brier']-x['elo_winner_brier'] for x in expanded]
            result['paired_intervals']['expanded_minus_elo_winner_brier']=bootstrap_diff(ds,[x['game_date'] for x in expanded])
        for alt in ('poisson','wide_nb','constant_nb'):
            result['paired_intervals'][alt+'_minus_validated_nb']={m:bootstrap_diff(
                [x[alt+'_'+m]-x['validated_nb_'+m] for x in rows],[x['game_date'] for x in rows])
                for m in ('exact_log_loss','total_crps','under_brier')}
    by_quote={x['quote_id']:x for x in quotes}
    evaluated=[]
    for b in paper:
        final=settled.get(b['game_id']);q=by_quote.get(b['quote_id'])
        if not final or not q:continue
        actual_home=int(final['home_final']);actual_away=int(final['away_final'])
        yes={'home_win':actual_home>actual_away,'away_win':actual_home<actual_away,
             'under_6_5':actual_home+actual_away<=6,'over_6_5':actual_home+actual_away>6}[b['market']]
        cost=(float(b['yes_ask_cents'])+float(b['estimated_fee_cents_per_contract']))/100
        pnl=(float(yes)-cost)*int(b['contracts'])
        evaluated.append({'game_id':b['game_id'],'market':b['market'],
                          'paper_pnl_usd':pnl,'paper_cost_usd':cost*int(b['contracts']),
                          'yes_won':bool(yes)})
    if evaluated:
        spend=sum(t['paper_cost_usd'] for t in evaluated)
        result['paper_trades']={'settled_entries':len(evaluated),'hypothetical_spend_usd':spend,
                               'hypothetical_pnl_usd':sum(t['paper_pnl_usd'] for t in evaluated),
                               'hypothetical_roi':sum(t['paper_pnl_usd'] for t in evaluated)/spend,
                               'real_money_claim':False,'individual_results':evaluated}
    return result,rows


def write_report(store=STORE):
    report,rows=analysis(store)
    dest=Path(store);dest.mkdir(parents=True,exist_ok=True)
    (dest/'prospective_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if rows:
        import csv
        with (dest/'prospective_graded_games.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=sorted({k for row in rows for k in row}),extrasaction='ignore')
            writer.writeheader();writer.writerows(rows)
    return report


def watch_day(day,store=STORE,root=ROOT,lead_minutes=60,interval_seconds=90,
              fetcher=None,sleeper=None,now_fn=None):
    """OPTIONAL foreground watcher. Saves pregame forecasts only while running.

    Does NOT monitor Kalshi, retrieve prices or place any order. This runs in
    the user's own terminal and ends after the day's final scheduled first pitch.
    """
    import time
    from forecast_engine import fetch_schedule,build_run_fit
    from extended_eval import all_games
    day=date.fromisoformat(str(day))
    if not 5<=lead_minutes<=1440:raise ValueError('lead_minutes must be 5..1440')
    if not 30<=interval_seconds<=3600:raise ValueError('interval_seconds must be 30..3600')
    fetcher=fetcher or fetch_schedule;sleeper=sleeper or time.sleep;now_fn=now_fn or utc_now
    run_fit=None;games=None;seen_game=False
    print('Foreground watcher started. Keep this PowerShell window open; Ctrl+C stops it.',flush=True)
    while True:
        now=parse_time(now_fn())
        try:
            official=fetcher(day)
        except Exception as exc:
            print('MLB schedule unavailable; no records created: '+str(exc),flush=True)
            sleeper(interval_seconds);continue
        if not official:
            print('No games returned for date '+day.isoformat()+'.',flush=True)
            return
        latest=max(parse_time(g['start_utc']) for g in official)
        if now>=latest:
            print('All scheduled first pitches passed. Watcher stopping.',flush=True)
            return
        previous={x['game_id'] for x in read_log(paths(store)['forecasts'])}
        for m in official:
            until=(parse_time(m['start_utc'])-now).total_seconds()/60
            if not 0<until<=lead_minutes or normal_id(m['id']) in previous:continue
            try:
                if games is None:
                    print('Loading frozen model and strict prior-game history...',flush=True)
                    games=all_games(Path(root)/'data',True)
                    run_fit=build_run_fit(Path(root)/'data')
                # freeze_game re-fetches status and kickoff just before storing.
                frozen=freeze_game(m,games,run_fit,store,root=root,refresh_fetcher=fetcher)
                print(f"FROZEN: {m['away']} at {m['home']} "
                      f"{frozen['created_at_utc']} ID={frozen['forecast_id']}",flush=True)
                previous.add(normal_id(m['id']))
            except Exception as exc:
                print('No forecast saved for '+str(m['id'])+': '+str(exc),flush=True)
        sleeper(interval_seconds)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',type=Path,default=STORE)
    sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('list');a.add_argument('--date',required=True)
    a=sub.add_parser('freeze');a.add_argument('--date',required=True);a.add_argument('--game-id',required=True)
    a=sub.add_parser('watch');a.add_argument('--date',required=True);a.add_argument('--lead-minutes',type=int,default=60);a.add_argument('--interval-seconds',type=int,default=90)
    a=sub.add_parser('quote');a.add_argument('--forecast-id');a.add_argument('--game-id');
    a.add_argument('--market',choices=MARKETS,required=True);a.add_argument('--ask-cents',type=float,required=True)
    a.add_argument('--fee-cents',type=float,required=True);a.add_argument('--attest',action='store_true')
    a=sub.add_parser('paper');a.add_argument('--quote-id',required=True)
    a=sub.add_parser('settle');a.add_argument('--date',required=True)
    sub.add_parser('report')
    args=parser.parse_args()
    if args.command=='list':
        from forecast_engine import fetch_schedule
        for g in fetch_schedule(date.fromisoformat(args.date)):
            print(f"{g['id']} | {g['away_name']} at {g['home_name']} | {g['start_utc']} | {g['status']}")
    elif args.command=='freeze':
        from forecast_engine import fetch_schedule,build_run_fit
        from extended_eval import all_games
        day=date.fromisoformat(args.date);match=find_official_game(args.game_id,day)
        record=freeze_game(match,all_games(ROOT/'data',True),build_run_fit(ROOT/'data'),
                           args.store,root=ROOT)
        print(json.dumps({k:v for k,v in record.items() if k not in ('scoring_distributions','scoring_summaries')},indent=2))
    elif args.command=='watch':
        try:watch_day(args.date,args.store,ROOT,args.lead_minutes,args.interval_seconds)
        except KeyboardInterrupt:print('Watcher stopped by user. No orders were placed.')
    elif args.command=='quote':
        fs=read_log(paths(args.store)['forecasts'])
        choices=[x for x in fs if (args.forecast_id and x['forecast_id']==args.forecast_id)
                or (args.game_id and x['game_id']==normal_id(args.game_id))]
        if len(choices)!=1:parser.error('Give a unique --forecast-id or --game-id of a frozen game')
        record=add_quote(choices[0]['forecast_id'],args.market,args.ask_cents,args.fee_cents,args.attest,args.store)
        print(json.dumps(record,indent=2))
    elif args.command=='paper':print(json.dumps(lock_paper_entry(args.quote_id,args.store),indent=2))
    elif args.command=='settle':print(json.dumps(settle(args.date,args.store),indent=2))
    elif args.command=='report':print(json.dumps(write_report(args.store),indent=2))

if __name__=='__main__':main()
