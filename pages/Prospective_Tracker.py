"""A Streamlit page for preregistered, timestamped MLB prediction research.

Only saves forecasts and quote observations before OFFICIAL scheduled first pitch.
It does not connect to Kalshi, execute orders or guarantee a fill.
"""
from __future__ import annotations
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
import sys
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from prospective_tracker import (STORE,paths,read_log,freeze_game,add_quote,lock_paper_entry,
    settle,write_report,parse_time,utc_now,normal_id)
from forecast_engine import fetch_schedule,build_run_fit,TEAM_NAMES
from extended_eval import all_games
from matchup_model import backtest_expanded,expanded_forecast

st.set_page_config(page_title='Prospective Tracker | MLB Prediction Lab',page_icon='🧪',layout='wide')
st.title('🧪 Prospective MLB Forecast Tracker')
st.caption('Local timestamped research journal • manual Kalshi buy-YES quotes • hypothetical paper entries • outcome verification')
st.warning('No trading, quote retrieval or broker integration. A saved quote is NOT a verified fill. '
    'Final-score and total-run probabilities remain experimental, and a few successful picks cannot establish an edge.')

@st.cache_data(ttl=40,show_spinner='Checking official MLB schedule…')
def games_today(iso):return fetch_schedule(date.fromisoformat(iso))

@st.cache_data(show_spinner='Loading MLB games…')
def history_cached(sig):return all_games(ROOT/'data',True)

@st.cache_resource(show_spinner='Training frozen 2023–24 score model…')
def run_cached(sig):return build_run_fit(ROOT/'data')

@st.cache_resource(show_spinner='Fitting research-only expanded matchup model…')
def expanded_cached(sig):return backtest_expanded(history_cached(sig),ROOT/'data',None)


def sig_data():
    import prospective_tracker as p
    names=p.DATA_FILES
    return tuple((n,(ROOT/'data'/n).stat().st_mtime_ns,(ROOT/'data'/n).stat().st_size)
                 for n in names if (ROOT/'data'/n).exists())


def all_saved():
    p=paths(STORE)
    return {name:read_log(path) for name,path in p.items()}


def tz_fmt(t):
    from zoneinfo import ZoneInfo
    return parse_time(t).astimezone(ZoneInfo('America/New_York')).strftime('%b %d %I:%M %p ET')


def display_game(g):
    return f"{g['away_name']} at {g['home_name']} · {tz_fmt(g['start_utc'])} · {g['status']}"

forecast_tab,quote_tab,paper_tab,results_tab=st.tabs([
    '🔒 Freeze pregame forecasts','💲 Record Kalshi price','🧾 Paper positions','📊 Settle & evaluate'])

with forecast_tab:
    st.markdown('### Lock a prediction before the game begins')
    st.caption('Re-fetches the official MLB schedule when you click Save. '
               'Any game past scheduled first pitch is BLOCKED, even if you can still inspect its research forecast elsewhere.')
    day=st.date_input('MLB game date',value=date.today(),min_value=date(2025,1,1),max_value=date(2026,12,31))
    match=None
    try:
        schedule=games_today(day.isoformat())
        if schedule:
            selected=st.selectbox('Official MLB game',schedule,format_func=display_game,
                                  key='pregame_game_select')
            match=selected
        else:st.info('No official games returned for this date.')
    except Exception as exc:
        st.error('Cannot certify an official matchup or start time. Logging is blocked until the schedule loads: '+str(exc))
    if match:
        time_left=(parse_time(match['start_utc'])-utc_now()).total_seconds()/60
        st.write(f"**Probable starters:** {match['away_pitcher']} vs. {match['home_pitcher']}")
        if time_left<=0:
            st.error('Pregame logging is locked: the officially scheduled start has passed. '
                     'Use Game forecasts for a historical research view, not as a timestamped pregame pick.')
        elif time_left>24*60:
            st.info('Return within 24 hours of first pitch to lock a more useful snapshot.')
        else:
            st.success(f'Pregame window open: approximately {time_left:.0f} minutes until scheduled first pitch.')
        try:
            frozen=next((x for x in read_log(paths(STORE)['forecasts'])
                         if x['game_id']==normal_id(match['id'])),None)
        except ValueError as exc:
            st.error(f'Audit log corrupted: {exc}');frozen=None
        if frozen:
            st.info('A frozen prediction already exists for this game. To avoid hindsight updates, no second forecast is permitted.')
            st.json({k:v for k,v in frozen.items() if k not in ('scoring_distributions','prev_hash','record_hash')},expanded=False)
        elif st.button('🔒 Save official pregame forecast',disabled=time_left<=0 or time_left>24*60,
                        type='primary',key='freeze_now'):
            try:
                with st.spinner('Rechecking game status, fitting frozen models, and recording full distributions…'):
                    sig=sig_data()
                    historic=history_cached(sig);fit=run_cached(sig)
                    adv=None
                    try:
                        _,model,_,hands,_=expanded_cached(sig)
                        adv=expanded_forecast(historic,day,match['home'],match['away'],model,
                                             hands,match.get('home_pitcher_id',''),
                                             match.get('away_pitcher_id',''),ROOT/'data')
                    except Exception as exc:
                        st.warning('Expanded model could not be attached; Elo and scoring forecasts remain available: '+str(exc))
                    saved=freeze_game(match,historic,fit,STORE,root=ROOT,expanded=adv)
                st.success('Saved an immutable local timestamped research record. Forecast ID: '+saved['forecast_id'])
                st.json({'capture_time_utc':saved['created_at_utc'],
                         'first_pitch_utc':saved['first_pitch_utc'],
                         'elo_home_win':saved['elo_home_win_probability'],
                         'research_expanded_home_win':(adv or {}).get('p_home_expanded'),
                         'validated_nb_score':saved['scoring_summaries']['validated_nb'],
                         'wide_nb_score':saved['scoring_summaries']['wide_nb']})
            except Exception as exc:st.error('Forecast was not recorded: '+str(exc))

with quote_tab:
    st.markdown('### Manually record an executable Kalshi BUY YES quote')
    st.caption('Open Kalshi yourself and inspect the BUY YES order ticket. A chart price, 1.64x payout label, '
               'portfolio valuation, sell quote, or speculative price is not an executable buy-YES ask.')
    try: fs=read_log(paths(STORE)['forecasts'])
    except ValueError as exc:fs=[];st.error(str(exc))
    eligible=[f for f in fs if parse_time(f['first_pitch_utc'])>utc_now()]
    if not eligible:st.info('First freeze a game before scheduled first pitch. No eligible games have been logged yet.')
    else:
        selected=st.selectbox('Frozen game',eligible,
            format_func=lambda f:f"{f['matchup']['away_name']} at {f['matchup']['home_name']} · {tz_fmt(f['first_pitch_utc'])}",
            key='quote_forecast')
        market=st.selectbox('Exact Kalshi contract',('home_win','away_win','under_6_5','over_6_5'),
            format_func=lambda x:{'home_win':selected['matchup']['home_name']+' win',
                                  'away_win':selected['matchup']['away_name']+' win',
                                  'under_6_5':'Under 6.5 total runs (YES)',
                                  'over_6_5':'Over 6.5 total runs (YES)'}[x])
        col1,col2=st.columns(2)
        ask=col1.number_input('Current BUY YES ask, cents for one $1 contract',1.0,99.0,60.0,0.5)
        fee=col2.number_input('Actual quoted/estimated fee, cents PER contract',0.0,99.0,1.0,0.1)
        attestation=st.checkbox('I viewed this exact BUY YES order-ticket ask and fee before first pitch. '
           'I understand that logging does not buy a contract or prove a fill.',value=False)
        if st.button('💾 Record pregame quote',disabled=not attestation or ask+fee>=100):
            try:
                rec=add_quote(selected['forecast_id'],market,ask,fee,attestation,STORE)
                st.success('Quote observation saved (NOT a fill). Quote ID: '+rec['quote_id'])
                a,b,c=st.columns(3)
                a.metric('Model YES probability',f"{rec['model_yes_probability']:.1%}")
                b.metric('Break-even incl. fee',f"{rec['implied_break_even_with_fee']:.1%}")
                c.metric('Model-implied EV / $1 payout',f"${rec['modeled_ev_per_1usd_contract']:+.3f}")
                st.warning('Theoretical EV is NOT a validated betting advantage. The under-6.5 model is especially uncertain.')
            except Exception as exc:st.error('Quote not saved: '+str(exc))

with paper_tab:
    st.markdown('### Paper-trade journal (zero real-money execution)')
    st.caption('Pre-commit one hypothetical $1-payout YES contract per game. The quote must already have been saved '
               'and the game must not have started. This is NOT a Kalshi order.')
    try:
        existing_quotes=read_log(paths(STORE)['quotes'])
        locked=read_log(paths(STORE)['paper_entries'])
    except ValueError as exc:existing_quotes=[];locked=[];st.error(str(exc))
    candidates=[x for x in existing_quotes if parse_time(x['first_pitch_utc'])>utc_now()
                and not any(y['game_id']==x['game_id'] for y in locked)]
    if not candidates:st.info('No eligible quotes. Record a pregame Kalshi quote first.')
    else:
        q=st.selectbox('Previously recorded quote',candidates,
            format_func=lambda x:f"Game {x['game_id']} · {x['market']} · {x['yes_ask_cents']:.1f}¢ + fee {x['estimated_fee_cents_per_contract']:.1f}¢")
        if st.button('🔒 Lock ONE hypothetical paper contract'):
            try:
                item=lock_paper_entry(q['quote_id'],STORE)
                st.success('Paper contract committed before first pitch. This did not place a trade: '+item['paper_id'])
            except Exception as exc:st.error(str(exc))

with results_tab:
    st.markdown('### Verify actual outcomes and prospective metrics')
    st.caption('Settles only verified FINAL MLB games. Outcomes never change frozen predictions. '
               'A meaningful confidence interval needs at least 30 games across 10 game dates.')
    result_date=st.date_input('Game date to check for official finals',date.today(),key='settle_date')
    if st.button('🔄 Check official FINAL scores and settle'):
        try:
            saved=settle(result_date.isoformat(),STORE)
            if saved:st.success(f'Settled {len(saved)} game(s) using verified final scores.')
            else:st.info('No new final scores for your frozen forecasts yet.')
        except Exception as exc:st.error('Settlement unavailable: '+str(exc))
    if st.button('📊 Recalculate prospective validation'):
        try:
            report=write_report(STORE)
            st.success('Saved results to outputs/prospective/prospective_report.json')
            st.json({k:v for k,v in report.items() if k!='paper_trades'})
        except Exception as exc:st.error('Prospective report failed: '+str(exc))
    try:
        logs=all_saved()
        st.caption(f"Current journal: {len(logs['forecasts'])} frozen games · "
                   f"{len(logs['quotes'])} quote observations · "
                   f"{len(logs['paper_entries'])} paper entries · {len(logs['results'])} official finals")
        if logs['forecasts']:
            st.dataframe(pd.DataFrame([{'Game ID':f['game_id'],
                                       'Matchup':f['matchup']['away_name']+' at '+f['matchup']['home_name'],
                                       'Saved UTC':f['created_at_utc'],
                                       'Elo home win':f['elo_home_win_probability'],
                                       'Official final': 'Yes' if any(r['game_id']==f['game_id'] for r in logs['results']) else 'Pending'}
                                      for f in logs['forecasts']]),hide_index=True,use_container_width=True)
    except Exception as exc:st.error('Audit log could not be read: '+str(exc))
    st.info('If a game has already begun, you can still examine its pregame-date model output in the main '
            'Game forecasts tab, but it cannot enter this prospective audit after the fact.')
