"""MLB Prediction Lab V5 | clean totals-first UI, detailed evidence when needed.

All wagers and selections require user action in external apps; no trading connection.
A data vendor's reference quote is not an executable buy ticket or model input.
"""
from __future__ import annotations
import os,sys,json,statistics
from pathlib import Path
from datetime import datetime,date,timezone
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import streamlit as st
from extended_eval import all_games
from forecast_engine import fetch_schedule,TEAM_NAMES
from v4_workflow import build_assets,generate
from v4_sources import capture_official_pregame
from v5_totals import (probabilities_for_line,representative_score,fair_decimal,
    decimal_to_american,american_to_decimal,kalshi_contract_edge,expected_unit_roi)
from v5_markets import (PROVIDERS,SPORTSBOOKS,DFS,fetch_book_odds,find_event,
    normalize_event_markets,totals_table_for_line,consensus_for_line,
    fetch_dfs_props,normalize_dfs_props)
from v5_pregame import parse_mlb_weather,is_verified_pregame,data_readiness
from v4_log import freeze
from v5_quote_log import record_manual_quote

st.set_page_config(page_title='MLB Totals Lab V5',page_icon='⚾',layout='wide')
st.title('⚾ MLB Totals Lab')
st.caption('One projected score · expected runs · winner · over/under any line · sportsbook, exchange & fantasy research')
st.info('Model probabilities are research estimates, not verified profitable edges. Quotes shown from aggregators are indicative, not guaranteed executable. No bets are placed.')
DATA=ROOT/'data'

@st.cache_data(show_spinner='Reading completed MLB games...')
def history_cache(sig):return all_games(DATA,True)

@st.cache_resource(show_spinner='Training the frozen 2023–2024 V4 run model...')
def assets_cache(sig):return build_assets(history_cache(sig),ROOT)

@st.cache_data(ttl=180,show_spinner=False)
def official_schedule(day):return fetch_schedule(date.fromisoformat(day))

@st.cache_data(ttl=180,show_spinner=False)
def official_context(game_id,start_utc):
    return capture_official_pregame(game_id,start_utc)

def sig():
    names=['GL2023.TXT','GL2024.TXT','GL2025.TXT','mlb_2026_regular.csv',
     'mlb_postseason_2023_2026.csv','advanced_pitching_details.csv',
     'pitcher_directory.csv','mlb_2026_fielding_errors.csv']
    return tuple((n,(DATA/n).stat().st_mtime_ns,(DATA/n).stat().st_size)
                 for n in names if (DATA/n).exists())

def game_key(game):return str(game.get('id') or f"{game.get('date')}:{game.get('away')}@{game.get('home')}")

def fmt_american(dec):
    try:return f'{decimal_to_american(float(dec)):+d}'
    except (ValueError,TypeError):return 'Unavailable'

selected_day=st.date_input('Game date',date.today(),min_value=date(2025,1,1))
source=st.radio('Matchup',['Official MLB schedule','Manual research'],horizontal=True)
match=None
if source=='Official MLB schedule':
    try:
        choices=official_schedule(selected_day.isoformat())
        if choices:
            match=st.selectbox('Game',choices,format_func=lambda g:
                f"{g['away_name']} at {g['home_name']} · {g['status']} · {g['start_utc']}")
        else:st.warning('No games returned for this date. Check date or use manual research.')
    except Exception as exc:st.error('MLB schedule unavailable. Try again or use Manual research.')
else:
    c1,c2=st.columns(2)
    with c1:away=st.selectbox('Away team',sorted(TEAM_NAMES),format_func=lambda x:TEAM_NAMES[x],
                             index=sorted(TEAM_NAMES).index('CLE'))
    with c2:home=st.selectbox('Home team',sorted(TEAM_NAMES),format_func=lambda x:TEAM_NAMES[x],
                             index=sorted(TEAM_NAMES).index('TBA'))
    match={'id':'','date':str(selected_day),'away':away,'home':home,
         'away_name':TEAM_NAMES[away],'home_name':TEAM_NAMES[home],
         'away_pitcher_id':'','home_pitcher_id':'','start_utc':'','game_type':'R',
         'status':'MANUAL RESEARCH - unverified starters'}
if not match:st.stop()
if match['home']==match['away']:st.error('Choose two different teams.');st.stop()
match_id=game_key(match)
if st.session_state.get('v5_match_id')!=match_id:
    st.session_state['v5_match_id']=match_id
    for key in ('v5_snapshot','v5_result','v5_odds','v5_odds_event','v5_dfs'):
        st.session_state.pop(key,None)

st.subheader(f"{match['away_name']} at {match['home_name']}")
start_ok=is_verified_pregame(match)
# Certified snapshots can only be fetched before first pitch; no lookahead.
if start_ok and 'v5_snapshot' not in st.session_state:
    try:st.session_state['v5_snapshot']=official_context(str(match['id']),str(match['start_utc']))
    except Exception:pass  # Incomplete MLB feeds should not prevent a neutral-data forecast.
if not start_ok:
    st.caption('Historical/post-start scenario: cannot label newly captured information as a pregame forecast.')

with st.expander('Game inputs · pitchers, confirmed lineups, bullpen, park & weather',expanded=False):
    st.write('**Probable starters:**',match.get('away_pitcher') or 'Unspecified','vs.',match.get('home_pitcher') or 'Unspecified')
    if st.button('Load MLB-verified pregame batting orders and bullpen IDs',disabled=not start_ok):
        try:st.session_state['v5_snapshot']=capture_official_pregame(match['id'],match['start_utc'])
        except Exception as exc:st.error(f'MLB pregame evidence unavailable: {exc}')
    snap=st.session_state.get('v5_snapshot')
    if snap:
        st.caption('MLB data captured '+snap['captured_utc']+' · '+str(snap.get('venue','Unknown venue')))
        st.write('Confirmed lineup coverage: away',len(snap['confirmed_lineups'].get('away',[])),
                 '/9 · home',len(snap['confirmed_lineups'].get('home',[])),'/9')
        mlb_weather=parse_mlb_weather(snap)
        st.write('Official weather:',mlb_weather['raw_weather'])
    else:mlb_weather={}
    apply_mlb_weather=st.checkbox('Apply MLB-reported weather sensitivity (experimental)',value=bool(mlb_weather.get('verified',False)),
        disabled=not mlb_weather.get('verified',False))
    park=st.checkbox('Apply historical home-park proxy (experimental; confirm venue first)',value=False)
    if park:st.warning('Park factor uses past home-team park results, not a verified causal stadium effect. Confirm this game uses the same stadium.')
    sims=st.select_slider('Monte Carlo games',[10000,30000,60000,100000],value=30000)
    st.caption('Lineup and weather adjustments are not validated to improve predictive accuracy. Missing inputs remain neutral.')

if st.button('Generate unified prediction',type='primary'):
    try:
        with st.spinner('Fitting and running matchup simulation...'):
            if apply_mlb_weather:
                w=parse_mlb_weather(st.session_state.get('v5_snapshot'))
            else:w={}
            result=generate(history_cache(sig()),ROOT,selected_day,match,
                assets=assets_cache(sig()),n=sims,
                official_snapshot=st.session_state.get('v5_snapshot'),
                park_enabled=park,temperature=w.get('temp'),wind_mph=w.get('wind_mph'),
                wind_direction=w.get('direction','neutral'),roof_closed=False)
        st.session_state['v5_result']=result
    except Exception as exc:st.error('Forecast failed; open the advanced project audit to investigate.');st.exception(exc)

r=st.session_state.get('v5_result')
if not r:
    st.caption('Press **Generate unified prediction** to see the projected winner, one final score, and total runs.')
    st.stop()
pred=r['forecast']
if 'total_pmf' not in pred:
    st.error('V5 run-distribution data is unavailable. Replace `v4_simulation.py` with the included V5 version.');st.stop()
line=st.number_input('Compare game total line (runs)',min_value=.5,max_value=20.5,value=6.5,step=.5)
prob=probabilities_for_line(pred['total_pmf'],line)
expected=pred['total_expected_runs']
win_side='home' if pred['home_win_probability']>=.5 else 'away'
win_team=match[win_side+'_name'];p_win=pred[win_side+'_win_probability']
score=representative_score(pred)

st.subheader('The forecast')
col1,col2,col3=st.columns(3)
col1.metric('PROJECTED TOTAL RUNS',f'{expected:.2f}')
col2.metric('OVER '+str(line),f"{prob['over']*100:.1f}%")
col3.metric('UNDER '+str(line),f"{prob['under']*100:.1f}%")
if prob['push']>0:st.caption(f"Push at exactly {line:g} runs: {prob['push']*100:.1f}% (staked amount returned where rules permit).")
margin=abs(prob['over']-prob['under'])
if margin<.06:lean='No meaningful model lean'
elif prob['over']>prob['under']:lean=f'Over {line:g} (model lean only)'
else:lean=f'Under {line:g} (model lean only)'
st.markdown(f'**Model total lean:** {lean}. Not a bet recommendation.')

p1,p2,p3=st.columns(3)
p1.metric('SIMULATED WINNER',win_team)
p2.metric('WIN PROBABILITY',f'{p_win*100:.1f}%')
p3.metric('ONE REPRESENTATIVE SCORE',f"{match['away'].upper()} {score['away']} – {match['home'].upper()} {score['home']}")
st.caption(f"Expected runs: {match['away_name']} {pred['away_expected_runs']:.2f}; {match['home_name']} {pred['home_expected_runs']:.2f}. "
    f"That exact score was only {score['probability']*100:.2f}% of simulated games; it is not a confident exact-score prediction. "
    f"Simulated 80% total-run range: {pred['total_80_range'][0]}–{pred['total_80_range'][1]}. "
    f"Monte Carlo sampling ±{pred['monte_carlo_95_half_width_pp']:.2f}pp on winner (excludes model uncertainty).")

st.subheader('Market comparison')
st.caption('Hard Rock Bet (Florida) · other U.S. books (reference only) · Kalshi (exchange) · Underdog & PrizePicks (fantasy/player picks). Never combine unmatched markets or different lines into a fake consensus.')

@st.cache_data(ttl=60,show_spinner=False)
def odds_cached(key):return fetch_book_odds(key)

with st.expander('Fetch sportsbook / exchange reference prices',expanded=False):
    st.caption('Optional API key from [The Odds API](https://the-odds-api.com/). This request consumes API credits and may require a paid plan for totals/specific books. No key or odds are bundled.')
    key=st.text_input('The Odds API key',type='password',value=os.environ.get('ODDS_API_KEY',''),help='Key stays in this Streamlit session; not included in downloaded reports or project files.')
    if st.button('Retrieve available game prices',disabled=not key):
        try:
            data=odds_cached(key)
            event=find_event(data,match['away_name'],match['home_name'],match.get('start_utc'))
            st.session_state['v5_odds_event']=event
            st.session_state['v5_odds']=normalize_event_markets(event)
            if not event:st.warning('No provider event matched both teams and this scheduled start. Nothing was estimated.')
        except Exception as exc:st.error(str(exc))
    st.caption('Book lines are indicative aggregator snapshots, NOT guaranteed live/executable bet prices. You must verify current platform eligibility and price.')

raw=st.session_state.get('v5_odds')
quotes=[]
if raw:
    table=totals_table_for_line(raw[0],line,prob)
    for x in table:
        quotes.append({'Provider':x['provider'],'Category':x['type'],'Line':f"{x['line']:g}",
        'Over odds':f"{fmt_american(x['over_decimal'])} ({x['over_decimal']:.2f}x)" if x.get('over_decimal') else '—',
        'Under odds':f"{fmt_american(x['under_decimal'])} ({x['under_decimal']:.2f}x)" if x.get('under_decimal') else '—',
        'Price timestamp (UTC)':x['updated_utc'],'Status':x['quote_status']})
    if quotes:
        st.dataframe(quotes,hide_index=True,use_container_width=True)
        consensus=consensus_for_line(table,line)
        if consensus is not None:
            st.caption(f"Reference sportsbook consensus at exactly {line:g}: {consensus*100:.1f}% no-vig OVER vs model {prob['over']*100:.1f}%. "
                'Consensus is not a validated blended model or actionable quote.')
    else:st.info('No comparable reference prices at your selected total line. Choose the actual listed line or enter a manual quote below.')
    available_lines=sorted(set(x['line'] for x in raw[0] if x.get('comparable')))
    if available_lines:st.caption('Posted sportsbook total lines in feed (these may differ by provider): '+', '.join(f'{x:g}' for x in available_lines))

with st.expander('All included platforms · access and data status',expanded=False):
    seen={q['provider_key'] for q in raw[0]} if raw else set()
    st.dataframe([{'Provider':name,'Type':category,
        'Game totals feed':'Shown' if key in seen else ('Player props only / separate market' if key in DFS else 'Not retrieved / no matching line'),
        'Availability':'Check platform and location rules' if key in DFS|{'kalshi'} else ('Florida licensed' if key=='hardrockbet_fl' else 'Other-state reference only')}
        for key,(name,category) in PROVIDERS.items()],hide_index=True,use_container_width=True)

with st.expander('Check Kalshi YES contract or manually entered sportsbook quote',expanded=False):
    mode=st.radio('Quote type',['Sportsbook total (decimal or American)','Kalshi $1 YES contract'],horizontal=True)
    which=st.radio('Contract direction',['Over','Under'],horizontal=True)
    mp=prob[which.lower()];push=prob['push']
    if mode.startswith('Sportsbook'):
        provider=st.selectbox('Provider', [k for k in PROVIDERS if k not in DFS|{'kalshi'}],
            format_func=lambda k:PROVIDERS[k][0])
        odds_format=st.radio('Odds format',['American','Decimal'],horizontal=True)
        if odds_format=='American':
            american=st.number_input('Actual listed American odds',value=-110,step=5)
            try:dec=american_to_decimal(american)
            except ValueError as exc:st.error(str(exc));dec=None
        else:
            dec=st.number_input('Decimal odds (includes stake)',min_value=1.01,max_value=100.,value=1.91,step=.01)
        if dec:
            roi=expected_unit_roi(mp,push,dec)
            fair=fair_decimal(mp,push)
            st.write(f'Implied break-even odds (accounting for pushes): {fmt_american(fair)} / {fair:.2f}x' if fair else 'Insufficient win probability')
            st.write(f'Model-implied return per $1 stake: **{roi:+.3f}** (unvalidated probability; NOT a demonstrated edge).')
        st.caption('Enter the current line and executable ticket odds yourself; a reference quote is not necessarily available to your location.')
        if dec and st.button('Record this manually observed pregame sportsbook quote',disabled=not start_ok):
            try:
                rec=record_manual_quote(match,PROVIDERS[provider][0],which,line,dec,'decimal',mp,
                        ROOT/'outputs'/'v5_manual_pregame_quotes.jsonl')
                st.success('Saved observation '+rec['sha256'][:12]+'. No trade was executed.')
            except Exception as exc:st.error(str(exc))
    else:
        st.caption('A single YES contract pays $1 if it resolves YES. Confirm the exact contract wording and use the executable buy-YES ask, not portfolio value or indicative odds.')
        ask=st.number_input('Executable BUY YES ask in cents',min_value=1.,max_value=99.,value=60.,step=1.)
        fee=st.number_input('Estimated all-in fee per contract (cents)',min_value=0.,max_value=30.,value=1.,step=.1)
        try:
            info=kalshi_contract_edge(mp,ask,fee)
            st.write(f"Break-even probability: **{info['break_even']*100:.1f}%** · research probability minus break-even **{info['probability_minus_break_even_pp']:+.1f}pp**.")
        except ValueError as exc:st.warning(str(exc))
        st.caption('Kalshi fees, fill price and resolution terms depend on the actual contract. The app never places trades.')
        if st.button('Record this manually observed pregame Kalshi quote',disabled=not start_ok):
            try:
                rec=record_manual_quote(match,'Kalshi',which,line,ask,'kalshi_yes_ask_cents',mp,
                        ROOT/'outputs'/'v5_manual_pregame_quotes.jsonl',fees=fee)
                st.success('Saved manual observation '+rec['sha256'][:12]+'. No trade was executed.')
            except Exception as exc:st.error(str(exc))

with st.expander('Underdog & PrizePicks player picks · separate comparison',expanded=False):
    st.caption('Player props and fantasy lineups are not comparable to full-game team totals. PrizePicks Team Picks and other event contracts can have different terms; verify those individually.')
    if st.session_state.get('v5_odds_event'):
        api_event=st.session_state['v5_odds_event']
        supplied=st.text_input('API key for DFS props',type='password',value=os.environ.get('ODDS_API_KEY',''),key='dfs_api_key')
        if st.button('Fetch available player props (uses extra API credits)',disabled=not supplied):
            try:
                payload=fetch_dfs_props(supplied,api_event['id'])
                st.session_state['v5_dfs']=normalize_dfs_props(payload)
            except Exception as exc:st.error(str(exc))
        dfs=st.session_state.get('v5_dfs')
        if dfs:st.dataframe(dfs[:100],hide_index=True,use_container_width=True)
        else:st.info('No DFS player props loaded. Availability depends on the vendor plan, sportsbook selection and event.')
    else:st.info('Load the game from the odds provider above before fetching DFS player props.')

with st.expander('Advanced matchup evidence, model assumptions and validation',expanded=False):
    st.dataframe(data_readiness(r),hide_index=True,use_container_width=True)
    st.write('Data coverage limitations:',r['data_gaps'] or 'No flagged gaps (individual overlays still experimental).')
    st.write('Park / weather source & applied multipliers:',r['adjustments'])
    st.write('Elo reference (separate model):',f"{r['baseline']['elo_home_win']*100:.1f}% home win")
    st.write('Model version:',r['model_version'],'·',pred['simulation_size'],'simulated games')
    st.write('Training note:',r.get('training'))
    st.caption('Team-level core trained 2023–24, with retrospective 2025 testing. Lineup, park/weather, bullpen roster and player overlays remain uncalibrated. This is not a real-time in-game win model.')
    st.download_button('Download forecast audit JSON',json.dumps(r,indent=2,default=str),
        file_name=f"v5_forecast_{selected_day}_{match['away']}_{match['home']}.json",mime='application/json')
    if st.button('Freeze this V5 pregame research forecast',disabled=not start_ok):
        try:
            rec=freeze(r,match['start_utc'],destination=ROOT/'outputs'/'v5_pregame_forecasts.jsonl')
            st.success('Saved before official first pitch: '+str(rec.get('record_hash_sha256',''))[:12])
        except Exception as exc:st.error(str(exc))

st.caption('No live wagering access or trades. When a game has started, this page can show retrospective pregame-only research, not an executable pregame pick.')
