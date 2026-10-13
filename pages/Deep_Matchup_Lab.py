"""MLB Prediction Lab V4: deep pregame matchup research (no auto trading)."""
from __future__ import annotations
import json,sys
from datetime import date,datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import streamlit as st
from extended_eval import all_games
from forecast_engine import TEAM_NAMES,fetch_schedule,quote_analysis
from v4_workflow import build_assets,generate
from v4_sources import capture_official_pregame
from v4_log import freeze

st.set_page_config(page_title='Deep Matchup Lab V4',page_icon='⚾',layout='wide')
st.title('⚾ Deep Matchup Lab — V4')
st.caption('Independent team scoring model · pitcher/hitter matchup evidence · reliever workload · park/weather scenarios · one unified inning simulation')
st.warning('Research predictions, NOT a proven betting advantage. Real player/lineup and environment effects are experimental overlays. The model does not access Kalshi or trade.')
DATA=ROOT/'data'

def signature():
    names=['GL2023.TXT','GL2024.TXT','GL2025.TXT','mlb_2026_regular.csv',
      'mlb_postseason_2023_2026.csv','advanced_pitching_details.csv','pitcher_directory.csv']
    return tuple((n,(DATA/n).stat().st_mtime_ns,(DATA/n).stat().st_size) for n in names if (DATA/n).exists())

@st.cache_data(show_spinner='Loading historical games...')
def history_cache(sig):return all_games(DATA,True)

@st.cache_resource(show_spinner='Fitting V4 matchup run model (frozen 2023–2024)...')
def asset_cache(sig):return build_assets(history_cache(sig),ROOT)

@st.cache_data(ttl=120,show_spinner='Loading official MLB schedule...')
def sched(day):return fetch_schedule(date.fromisoformat(day))

st.subheader('1 · Select your matchup')
a,b=st.columns([1,2])
with a:
    day=st.date_input('Game date',date.today(),min_value=date(2025,1,1),max_value=date(2026,12,31))
with b:
    source=st.radio('Matchup type',['Official MLB schedule','Manual research scenario'],horizontal=True)
match=None
if source.startswith('Official'):
    try:
        games_on_day=sched(day.isoformat())
        if not games_on_day:st.info('No MLB games returned for this date; use manual research if needed.')
        else:
            match=st.selectbox('Official matchup',games_on_day,format_func=lambda g:
             f"{g['away_name']} at {g['home_name']} · {g['status']} · {g['start_utc']}")
    except Exception as exc:st.error('Official schedule could not be loaded: '+str(exc))
else:
    first,second=st.columns(2)
    with first:home=st.selectbox('Home team',list(TEAM_NAMES),format_func=lambda x:TEAM_NAMES[x],index=list(TEAM_NAMES).index('TBA'))
    with second:away=st.selectbox('Away team',list(TEAM_NAMES),format_func=lambda x:TEAM_NAMES[x],index=list(TEAM_NAMES).index('CLE'))
    match={'id':'','home':home,'away':away,'home_name':TEAM_NAMES[home],'away_name':TEAM_NAMES[away],
        'home_pitcher_id':'','away_pitcher_id':'','home_pitcher':'Unspecified','away_pitcher':'Unspecified',
        'game_type':'R','start_utc':'','status':'UNVERIFIED MANUAL SCENARIO'}
if not match:st.stop()
if match['home']==match['away']:
    st.error('Home and away teams must differ.');st.stop()
start=None
if match.get('start_utc'):
    try:start=datetime.fromisoformat(match['start_utc'].replace('Z','+00:00'))
    except Exception:pass
started=(start is None or datetime.now(timezone.utc)>=start)
if started:
    st.info('Research/historical scenario only. No NEW pregame snapshots or prospective logs can be certified after scheduled first pitch (or without a verified start time).')
else:st.success('Official start has not passed. You may capture the MLB-confirmed starting lineup if announced.')

st.subheader('2 · Verified lineups and adjustable conditions')
key='v4_pregame_'+str(match.get('id',''))
if 'v4_game_key' not in st.session_state or st.session_state.v4_game_key!=key:
    st.session_state.v4_game_key=key
    st.session_state.pop('v4_snapshot',None)
    st.session_state.pop('v4_result',None)
if st.button('Load confirmed pregame lineups & bullpen roster from MLB',disabled=started):
    try:
        ss=capture_official_pregame(match['id'],match['start_utc'])
        st.session_state['v4_snapshot']=ss
        if not all(ss['is_official_lineup'].values()):
            st.warning('Official lineup not yet complete. Missing side(s) will use neutral lineup adjustment.')
        else:st.success('Both nine-player lineups confirmed at capture time.')
    except Exception as exc:st.error(str(exc))
snapshot=st.session_state.get('v4_snapshot')
if snapshot:
    st.caption('Pregame MLB feed captured at '+snapshot['captured_utc']+' · Venue: '+snapshot['venue'])
    for side in ('away','home'):
        players=snapshot['confirmed_lineups'].get(side,[])
        st.caption(f"{match[side+'_name']}: {len(players)}/9 official hitters · {len(snapshot['bullpen_ids'].get(side,[]))} bullpen IDs")
        if players:
            with st.expander(match[side+'_name']+' batting order'):
                st.dataframe(players,use_container_width=True,hide_index=True)

c1,c2,c3=st.columns(3)
with c1:
    allow_park=st.toggle('Apply historical home-park proxy',value=False,
      help='2023-24 home-game scoring proxy only; does not verify current venue or causal park effect.')
    park_manual=st.number_input('Manual park factor (1.00 means none)',min_value=.8,max_value=1.2,value=1.,step=.01)
with c2:
    use_weather=st.toggle('Apply weather scenario',value=False)
    temp=st.number_input('Temperature °F',min_value=0,max_value=125,value=70,disabled=not use_weather)
    closed=st.checkbox('Roof closed',value=False,disabled=not use_weather)
with c3:
    wind=st.number_input('Wind mph',min_value=0,max_value=60,value=0,disabled=not use_weather)
    direction=st.selectbox('Wind orientation',['neutral','out','in'],disabled=not use_weather)
    sims=st.select_slider('Game simulations',[10000,30000,60000,100000],value=30000)
st.caption('Park and weather factors are bounded and uncalibrated; the neutral scenario is the recommended reference. Official weather is not guaranteed available in MLB feeds.')

if st.button('⚾ Simulate this matchup',type='primary'):
    try:
        sig=signature();history=history_cache(sig);assets=asset_cache(sig)
        with st.spinner('Running unified inning simulation...'):
            result=generate(history,ROOT,day,match,assets,n=sims,
                official_snapshot=snapshot,
                park_enabled=allow_park,park_override=(park_manual if park_manual!=1 else None),
                temperature=(temp if use_weather else None),
                wind_mph=(wind if use_weather else None),
                wind_direction=(direction if use_weather else 'neutral'),
                roof_closed=closed)
        st.session_state['v4_result']=result
    except Exception as exc:
        st.exception(exc)
r=st.session_state.get('v4_result')
if r:
    pred=r['forecast'];st.divider();st.subheader('3 · Unified game forecast')
    h,a=st.columns(2)
    h.metric(match['home_name']+' wins',f"{100*pred['home_win_probability']:.1f}%")
    a.metric(match['away_name']+' wins',f"{100*pred['away_win_probability']:.1f}%")
    st.caption(f"Elo benchmark: {100*r['baseline']['elo_home_win']:.1f}% home. V4 is independent; it does NOT force the final score to agree with Elo. Monte Carlo 95% sampling half-width: ±{pred['monte_carlo_95_half_width_pp']:.2f} percentage points (not a model confidence interval).")
    metrics=st.columns(4)
    metrics[0].metric('Home projected runs',f"{pred['home_expected_runs']:.2f}")
    metrics[1].metric('Away projected runs',f"{pred['away_expected_runs']:.2f}")
    metrics[2].metric('Expected total',f"{pred['total_expected_runs']:.2f}")
    metrics[3].metric('Under 6.5',f"{100*pred['under_6_5_probability']:.1f}%")
    st.write('**80% simulated score ranges:** home',str(pred['home_80_range']),', away',str(pred['away_80_range']),', combined',str(pred['total_80_range']))
    st.markdown('**Most frequent exact scores** (not high-probability guarantees)')
    st.dataframe([{'Away runs':x['away'],'Home runs':x['home'],
       'Estimated frequency':f"{x['probability']*100:.2f}%"} for x in pred['modal_exact_scores']],
       hide_index=True,use_container_width=True)
    st.subheader('4 · Matchup-specific evidence')
    for side in ('away','home'):
        s=r['personnel'][side]
        with st.expander(f"{match[side+'_name']} — starter, lineup and bullpen",expanded=True):
            st.write('**Probable starter:**',match.get(side+'_pitcher') or 'Unannounced')
            st.json(s['starter'],expanded=False)
            st.write('**Confirmed lineup:**',len(s['lineup']),'hitters ·',s['lineup_adjustment']['status'])
            if s['lineup']:st.dataframe(s['lineup_batters'],hide_index=True,use_container_width=True)
            st.write('**Reliever evidence:**',s['bullpen']['status'],f"· estimated prior-use ERA {s['bullpen']['era']:.2f}")
            if s['bullpen']['profiles']:st.dataframe(s['bullpen']['profiles'][:10],hide_index=True,use_container_width=True)
    st.write('**Park:**',r['adjustments']['park'])
    st.write('**Weather:**',r['adjustments']['weather'])
    if r['data_gaps']:
        st.warning('Coverage limitations: '+'; '.join(r['data_gaps']))
    st.subheader('5 · Compare with a manual Kalshi YES quote')
    st.caption('Input the buy-YES ask from your Kalshi ORDER TICKET, not the portfolio price or displayed payout multiple. This does not fetch quotes or place orders.')
    q1,q2,q3=st.columns(3)
    with q1:market=st.selectbox('Contract',['Home wins','Away wins','Under 6.5','Over 6.5'])
    with q2:ask=st.number_input('Actual YES ask (cents)',min_value=1.,max_value=99.,value=60.,step=1.)
    with q3:fees=st.number_input('Fees per $1 contract (cents)',min_value=0.,max_value=40.,value=1.,step=.1)
    lookup={'Home wins':pred['home_win_probability'],'Away wins':pred['away_win_probability'],
            'Under 6.5':pred['under_6_5_probability'],'Over 6.5':pred['over_6_5_probability']}
    try:
        q=quote_analysis(lookup[market],ask,fees)
        st.metric('Model probability minus break-even',f"{q['edge_pp']:+.1f} percentage points")
        st.caption('This is arithmetic conditional on the exploratory model probability, NOT proven expected profit. Fees and quotes must reflect an executable contract.')
    except ValueError as exc:st.error(str(exc))
    with st.expander('Full source and model audit'):
        st.json({k:v for k,v in r.items() if k not in ('personnel','match')},expanded=False)
    st.download_button('Download this research forecast (JSON)',
        data=json.dumps(r,indent=2,default=str),file_name=f'v4_{day}_{match["away"]}_{match["home"]}.json',mime='application/json')
    if st.button('🔒 Freeze this pregame forecast in local research log',disabled=started or not str(match.get('id','')).isdigit()):
        try:
            saved=freeze(r,match['start_utc'],destination=ROOT/'outputs'/'v4_pregame_forecasts.jsonl')
            st.success('Frozen before official first pitch: '+saved['record_hash_sha256'][:12])
        except Exception as exc:st.error(str(exc))

st.divider()
st.subheader('6 · Historical validation')
report=ROOT/'outputs'/'v4_model_validation.json'
if report.exists():
    result=json.loads(report.read_text())
    st.caption('Frozen 2023–24 run model; 2025 and 2026 retrospective holdouts; any extra lineup/weather/park effects NOT validated in this report.')
    data=[]
    for key,entry in result.get('validation',{}).items():
        if entry.get('games'):
            data.append({'Split':key,'Games':entry['games'],
                'V4 run MAE':round(entry['team_run_mae'],3),
                'Constant-run MAE':round(entry['constant_4_5_run_mae'],3),
                'Improvement':round(entry['mae_improvement'],3)})
    st.dataframe(data,hide_index=True,use_container_width=True)
else:st.info('Run `py v4_validate.py --as-of 2026-10-13` to generate a historical validation report.')
st.caption('Before first pitch, make a prospectively frozen record. Don’t switch models because one playoff result looked favorable. Kalshi fills and profits are not tracked automatically.')
