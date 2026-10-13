"""MLB Prediction Lab V6 — a single, clean forecast board.

Launch from a separate nested directory for a baseball-only dashboard.
Only baseball inputs are loaded; no external price feed is consulted.
"""
from __future__ import annotations
import html
import sys
from datetime import date,datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

import streamlit as st
from extended_eval import all_games
from forecast_engine import fetch_schedule,TEAM_NAMES
from v4_workflow import build_assets,generate
from v4_sources import capture_official_pregame
from v5_pregame import parse_mlb_weather,is_verified_pregame,data_readiness
from v6_display import display_forecast
from v6_strength import team_indices,pregame_history_only
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_score_grid import heatmap_html
from v63_postseason import load_years
from v64_pitcher_audit import explain_starters

st.set_page_config(page_title='MLB Forecast | Prediction Lab',page_icon='⚾',layout='wide',initial_sidebar_state='collapsed')

st.markdown('''<style>
/* A one-board app, separate from the previous multi-page research lab. */
:root {color-scheme:dark;}
[data-testid="stAppViewContainer"] {background: radial-gradient(circle at 90% 8%, #142d38 0%, #0b121c 38%, #090e17 85%);}
[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:1130px; padding-top:2rem; padding-bottom:5rem;}
h1,h2,h3,p {letter-spacing:-.015em;}
.v6-brand {display:flex; align-items:center;justify-content:space-between;gap:1rem;padding:0 0 1.25rem;border-bottom:1px solid #283343;margin-bottom:1.5rem}
.v6-brand-name {font-size:1.35rem;font-weight:850;letter-spacing:-.04em;color:#f2f7fb}
.v6-brand-small {font-size:.74rem;color:#95a8b9;letter-spacing:.13em;font-weight:700}
.v6-chip {font:600 .72rem sans-serif;background:#142935;border:1px solid #2e5259;color:#9bdfce;border-radius:30px;padding:.55rem .8rem}
.v6-eyebrow {font:700 .76rem sans-serif;letter-spacing:.15em;color:#8bd8c6;text-transform:uppercase}
.v6-hero {border:1px solid #344453;border-radius:20px;background:linear-gradient(125deg,#182737,#121c29 50%,#101b26 100%); padding:1.5rem 1.8rem 1.6rem;margin:1rem 0 1.3rem;box-shadow:0 24px 50px #03091155}
.v6-hero-title {font-size:.85rem;color:#aebfcb;margin:0 0 1.25rem}
.v6-board {display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:1.4rem}
.v6-team {font-size:clamp(1.0rem,2.1vw,1.65rem);font-weight:750;color:#f0f8fb;line-height:1.22}
.v6-team small {display:block;color:#93a6b7;letter-spacing:.13em;font-size:.64rem;margin-bottom:.6rem}
.v6-team.right {text-align:right}
.v6-team-wrap {display:flex;align-items:center;gap:.7rem;}
.v6-team.right .v6-team-wrap {flex-direction:row-reverse;}
.v6-team-mark {flex:none;display:grid;place-items:center;min-width:49px;height:49px;padding:0 .4rem;border-radius:12px;background:linear-gradient(140deg,#235d63,#1b333e);border:1px solid #3c7973;color:#c9fff0;font-size:.79rem;font-weight:850;letter-spacing:.025em}
.v6-team-word {overflow-wrap:break-word;}
.v6-score {font-size:clamp(2.5rem,5.5vw,5.25rem);font-weight:850;letter-spacing:-.065em;color:#fbfff9;white-space:nowrap;line-height:1}
.v6-sub-score {text-align:center;color:#9fb0bf;font-size:.8rem;margin-top:1.2rem}
.v6-total {display:flex;align-items:center;justify-content:space-between;gap:1rem;border-top:1px solid #3a4c5b;margin-top:1.35rem;padding-top:1rem}
.v6-total strong {font-size:1.7rem;color:#c6f1db;letter-spacing:-.035em}
.v6-total-label {font-weight:600;color:#bec9d2;font-size:.89rem}
.v6-meta {color:#9daeb9;font-size:.75rem;line-height:1.55}
.v6-section {font-size:1rem;font-weight:800;color:#f2f7fb;margin:1.6rem 0 .5rem}
.v6-bar {display:flex;width:100%;height:13px;border-radius:20px;overflow:hidden;background:#283340;margin:.65rem 0}
.v6-over {background:#65d3b5;height:100%}
.v6-under {background:#5384b8;height:100%}
.v6-lean {padding:.9rem 1.1rem;border:1px solid #2b4d4b;background:#132928;border-radius:12px;color:#daf7e9;margin:1.1rem 0;font-size:.9rem}
.v6-desc {color:#a6b7c4;font-size:.82rem}
.v6-note {font-size:.78rem;color:#9aaebb}

/* Head-to-head ratings and score-grid visual language inspired by the supplied soccer-video reference. */
.v6-ratings {display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1.2rem 0 1.1rem;}
.v6-rating-card {background:#121e2a;border:1px solid #354754;border-radius:16px;padding:1.1rem 1.3rem;}
.v6-rating-name {font-weight:750;font-size:.95rem;color:#f2f7f9;margin-bottom:.8rem;}
.v6-rating-body {display:flex;justify-content:space-between;gap:.75rem;flex-wrap:wrap;}
.v6-rating-val {color:#eaf8fa;font-size:1.5rem;font-weight:800;letter-spacing:-.04em}
.v6-rating-body small {display:block;color:#8da4b7;font-size:.64rem;letter-spacing:.08em;margin-bottom:.35rem;text-transform:uppercase}
.v6-ratings-note {color:#95aaba;font-size:.73rem;margin:-.25rem 0 1rem}
.v6-heat-scroller {overflow-x:auto;max-width:100%;padding:.35rem 0 .8rem}
.v6-heat-table {display:grid;grid-template-columns:110px repeat(11,minmax(45px,1fr));gap:4px;min-width:685px;}
.v6-grid-head {display:flex;align-items:center;justify-content:center;color:#aec0ca;font-size:.74rem;font-weight:750;min-height:34px}
.v6-grid-corner {font-size:.58rem;letter-spacing:.04em;text-align:center}
.v6-heat-cell {min-height:35px;display:flex;justify-content:center;align-items:center;border-radius:5px;color:#e6fff3;font-size:.66rem;font-variant-numeric:tabular-nums;}
.v6-heat-active {outline:2px solid #fff;outline-offset:-2px;color:#fff;font-weight:900;}
.v6-exact-note {color:#9fb5bf;margin-top:.7rem;font-size:.78rem}
.v6-keypoint {font-weight:650;color:#c5eeda}
@media(max-width:730px){.v6-ratings {grid-template-columns:1fr}.v6-hero {padding:1.0rem}.v6-team {font-size:.85rem}.v6-team-mark {min-width:30px;height:32px;font-size:.6rem}.v6-score{font-size:2.1rem}.v6-board{gap:.4rem}.v6-rating-body{gap:.35rem}.v6-rating-val{font-size:1.4rem}.v6-total strong {font-size:1.15rem}}

div[data-testid="stMetric"] {border:1px solid #314050;border-radius:14px;padding:12px 17px;background:#131f2a;}
div[data-testid="stMetricValue"] {font-size:1.65rem;}
</style>''',unsafe_allow_html=True)

st.markdown('''<div class="v6-brand">
<div><div class="v6-brand-name">◉ &nbsp; MLB FORECAST LAB</div><div class="v6-brand-small">MATCHUP INTELLIGENCE · VIDEO-INSPIRED V6</div></div>
<div class="v6-chip">BASEBALL DATA ONLY</div></div>''',unsafe_allow_html=True)

DATA=ROOT/'data'

@st.cache_data(show_spinner='Loading prior MLB games...')
def history_cache(signature):return all_games(DATA,True)

@st.cache_resource(show_spinner='Preparing frozen matchup model...')
def assets_cache(signature):return build_assets(history_cache(signature),ROOT)

@st.cache_data(ttl=120,show_spinner=False)
def schedule_cache(day):return fetch_schedule(date.fromisoformat(day))

@st.cache_data(ttl=180,show_spinner=False)
def official_context(game_id,start_utc):return capture_official_pregame(game_id,start_utc)


def history_signature():
    files=['GL2023.TXT','GL2024.TXT','GL2025.TXT','mlb_2026_regular.csv',
           'mlb_postseason_2023_2026.csv','advanced_pitching_details.csv',
           'pitcher_directory.csv','mlb_2026_fielding_errors.csv']
    return tuple((f,(DATA/f).stat().st_mtime_ns,(DATA/f).stat().st_size)
                 for f in files if (DATA/f).exists())


def game_identity(match):
    return (str(match.get('id')),str(match['date']),match['away'],match['home'],str(match.get('start_utc','')))


def clean_name(s):return html.escape(str(s))

def team_mark(code):return html.escape(str(code).upper(),quote=True)

st.markdown('<div class="v6-eyebrow">01 / Select a game</div>',unsafe_allow_html=True)
cols=st.columns([1.05,1.6,1.1])
with cols[0]:day=st.date_input('Game date',value=date.today(),min_value=date(2025,1,1),max_value=date(2028,12,31))
with cols[1]:mode=st.radio('Game source',['MLB schedule','Manual matchup'],horizontal=True)
if mode=='MLB schedule':
    try:games=schedule_cache(day.isoformat())
    except Exception:games=[];st.warning('The official MLB schedule is unavailable. Choose Manual matchup to continue.')
    if not games:
        st.info('No official games were found on this date; select another date or use Manual matchup.')
        st.stop()
    with cols[2]:
        st.caption('Schedule loaded')
        st.caption(f'{len(games)} game(s)')
    match=st.selectbox('Matchup',games,format_func=lambda g:f"{g['away_name']}  @  {g['home_name']}  ·  {g['status']}")
else:
    a,h=st.columns(2)
    with a:away=st.selectbox('Away team',sorted(TEAM_NAMES),format_func=lambda x:TEAM_NAMES[x],index=sorted(TEAM_NAMES).index('LAN'))
    with h:home=st.selectbox('Home team',sorted(TEAM_NAMES),format_func=lambda x:TEAM_NAMES[x],index=sorted(TEAM_NAMES).index('MIL'))
    game_context=st.radio('Game type',['Regular season','Postseason'],horizontal=True)
    match={'id':'','date':day.isoformat(),'away':away,'home':home,'away_name':TEAM_NAMES[away],
           'home_name':TEAM_NAMES[home],'away_pitcher_id':'','home_pitcher_id':'',
           'away_pitcher':'Unverified','home_pitcher':'Unverified',
           'start_utc':'','game_type':'R' if game_context=='Regular season' else 'L','status':'MANUAL RESEARCH'}
if match['home']==match['away']:
    st.error('Choose two different teams.')
    st.stop()

match_key=game_identity(match)
if st.session_state.get('v6_current_game')!=match_key:
    st.session_state['v6_current_game']=match_key
    for k in ('v6_result','v6_snapshot'):
        st.session_state.pop(k,None)

pregame=is_verified_pregame(match)
if not pregame:st.caption('Historical replay: no certified pregame forecast was saved for this game. A replay generated today is NOT a pregame prediction.')

with st.expander('Model options & data coverage',expanded=False):
    st.caption('The core scoring model uses past-only game results; lineup, weather and park effects are experimental.')
    st.write('**Schedule-listed pitchers** ·',match.get('away_pitcher') or 'Unknown','vs.',match.get('home_pitcher') or 'Unknown')
    if not pregame:
        st.caption('For past games, schedule-listed starters may have been updated after first pitch. They are not independently verified as pregame information.')
        use_historical_starters=st.checkbox('Retrospective what-if: use schedule-listed starters',value=False,
                                            help='OFF is a more conservative historical replay. ON explores a matchup with starter identities obtained after the game; it is not a genuine pregame test.')
    snap=st.session_state.get('v6_snapshot')
    if pregame and snap is None:
        try:
            snap=official_context(str(match['id']),str(match['start_utc']))
            st.session_state['v6_snapshot']=snap
        except Exception:pass
    if pregame and st.button('Refresh verified pregame lineup & bullpen'):
        try:
            snap=capture_official_pregame(str(match['id']),str(match['start_utc']))
            st.session_state['v6_snapshot']=snap
            st.success('Official pregame data refreshed')
        except Exception as exc:st.warning(f'Pregame evidence unavailable: {exc}')
    if snap:
        counts={s:len(snap.get('confirmed_lineups',{}).get(s) or []) for s in ('away','home')}
        st.caption(f"Official lineup coverage: away {counts['away']}/9, home {counts['home']}/9 · captured {snap.get('captured_utc','?')}")
    else:st.caption('Verified pregame lineup unavailable; lineup-specific adjustments will remain neutral.')
    postseason_enabled=st.checkbox('Use postseason scoring context (research scenario)',
        value=True,disabled=str(match.get('game_type','R'))=='R',
        help='Historical league postseason run suppression; not a proven causal adjustment. ' 
             'Compare ON and OFF to measure its effect.')
    current_snapshot_allowed=(day.isoformat()>='2026-10-12' and day.year==2026)
    use_current_snapshot=st.checkbox('Include published 2026 playoff scoring trend',
        value=True,disabled=not current_snapshot_allowed,
        help='The 2026 league scoring snapshot was published before Oct 12. ' 
             'For earlier games it is ALWAYS barred to prevent lookahead.')
    use_park=st.checkbox('Apply experimental historical park factor',value=False)
    weather=parse_mlb_weather(snap)
    use_weather=st.checkbox('Apply experimental official-weather sensitivity',value=False,
                            disabled=not weather['verified'])
    sims=st.select_slider('Simulated games',[10000,30000,60000,100000],value=30000)

cta,caption=st.columns([1,2])
with cta:clicked=st.button('Run matchup forecast  →',type='primary',use_container_width=True)
with caption:st.caption('The same simulated games determine the winner, projected runs, and O/U probabilities.')

use_historical_starters=locals().get('use_historical_starters',False)
scenario_key=(match_key,bool(use_park),bool(use_weather),bool(use_historical_starters),
              bool(postseason_enabled),bool(use_current_snapshot),int(sims))
if clicked:
    try:
        w=weather if use_weather else {}
        research_match=clean_game_input(match,verified_pregame=pregame,
                                        historical_starters=use_historical_starters)
        with st.spinner('Analyzing pitchers, bullpen history, team offense and game simulations...'):
            safe_assets=historical_cutoff_assets(assets_cache(history_signature()),day)
            result=generate(pregame_history_only(history_cache(history_signature()),day),ROOT,day,research_match,
                assets=safe_assets,n=sims,
                official_snapshot=st.session_state.get('v6_snapshot'),park_enabled=use_park,
                temperature=w.get('temp'),wind_mph=w.get('wind_mph'),
                wind_direction=w.get('direction','neutral'),roof_closed=False,
                postseason_context_enabled=postseason_enabled,
                include_2026_snapshot=use_current_snapshot)
        st.session_state['v6_result']=(scenario_key,result)
    except Exception as exc:
        st.error('Forecast could not run. Expand the technical error to diagnose it.')
        with st.expander('Technical error'):st.exception(exc)

saved=st.session_state.get('v6_result')
if not saved or saved[0]!=scenario_key:
    st.info('Choose a game and click **Run matchup forecast** to see your prediction.')
    st.stop()
result=saved[1];pred=result['forecast']
# Make hidden starter effects (or missing starter history) visible before any
# over/under inference. Historic replays can be neutral when no starter proof.
impact=result.get('adjustments',{}).get('starter_total_rate',{})
impact_audit=impact.get('audit',{})
if impact:
    applied=[side for side in ('home','away') if impact_audit.get(side,{}).get('starter_applied')]
    if applied:
        total_before=sum(float(impact_audit[side]['previously_learned_rate']) for side in ('home','away'))
        total_after=sum(float(impact_audit[side]['adjusted_rate']) for side in ('home','away'))
        st.caption(f"Starter run-rate correction (2024-selected, experimental): {total_before:.2f} → {total_after:.2f} expected 9-inning runs. Available pitcher histories: away opponent {impact_audit.get('home',{}).get('prior_starts_with_details',0)}, home opponent {impact_audit.get('away',{}).get('prior_starts_with_details',0)}.")
    else:
        st.warning('Starting-pitcher impact is NOT changing the total in this run. Either the verified pitcher histories are absent or the 2024 calibration selected zero adjustment. Do not interpret the projected total as a full ace-vs-ace analysis.')
    with st.expander('Starter-adjustment evidence & calibration (research only)',expanded=False):
        st.write({'status':impact.get('calibration_status'),'weight':impact.get('weight'),'by_offense':impact_audit})
else:
    st.warning('This model does not report whether the starting pitchers affected game totals. Install the V6.2 starter calibration patch.')


# League-wide postseason environment is reported separately from starter effects.
post=result.get('adjustments',{}).get('postseason_scoring',{})
if post.get('active'):
    prev=post.get('run_model_before',{}).get('combined')
    now=post.get('run_model_after',{}).get('combined')
    st.info(f"October scoring context (research scenario): pregame regulation run means "
            f"{float(prev):.2f} → {float(now):.2f} after applying a "
            f"{float(post.get('factor',1)):.3f} postseason factor. "
            f"2026 Oct 11 snapshot included: {'YES' if post.get('current_2026_snapshot_used') else 'NO'}. "
            "The displayed FINAL-score mean may differ because of bottom-ninth and extra-inning effects.")
    with st.expander('Postseason dataset and no-lookahead audit (research only)',expanded=False):
        st.json(post)
        st.dataframe(load_years(DATA/'postseason_context_2022_2026.csv'),hide_index=True,use_container_width=True)
        st.caption('Scoring rates are per TEAM/game, not both teams combined. ' 
                   'Reliever share, home run and velocity numbers are user-supplied and diagnostic only; ' 
                   'they are not three extra scoring multipliers.')

# V6.4: a legible, game-specific audit. The same rates used for the
# forecast are shown relative to neutralized opponent-starter features.
# This does NOT retrofit the model to a completed game's actual final score.
try:
    starter_why=explain_starters(result)
except (ValueError,KeyError,TypeError) as error:
    starter_why={'available':False,'reason':str(error)}
if starter_why.get('available'):
    st.markdown('<div class="v6-section">How much did the starting pitchers change the projected total?</div>',unsafe_allow_html=True)
    m1,m2,m3=st.columns(3)
    m1.metric('Neutral-starter scenario · regulation',f"{starter_why['neutral_regulation_total']:.2f} runs")
    m2.metric('Selected starters · regulation',f"{starter_why['selected_regulation_total']:.2f} runs")
    m3.metric('Starting-pitcher adjustment',f"{starter_why['pitcher_total_delta']:+.2f} runs")
    st.caption(f"The original learned pitcher effect accounts for {starter_why['learned_pitcher_total_delta']:+.2f} runs and "
      f"the added V6.2 correction for {starter_why['extra_calibration_total_delta']:+.2f}. "
      f"Calibrated correction weight: {starter_why['calibration_weight']:.2f}. "
      "These are model counterfactuals for regulation, not guaranteed total runs or a causal estimate.")
    if abs(starter_why['pitcher_total_delta']) < .35:
        st.warning('The two selected starting pitchers have a SMALL modeled effect on this forecast. Do not interpret the matchup as fully pitching-adjusted merely because two ace names appear.')
    with st.expander('Starter-by-starter scoring explanation',expanded=False):
        for bat_side,bowl_side in [('away','home'),('home','away')]:
            r=starter_why['sides'][bat_side]
            name=match.get(bowl_side+'_pitcher') or 'Unverified starter'
            st.markdown(f"**{name} facing the {match[bat_side+'_name']} offense**")
            st.write({'previous_starts':r['prior_starts'],'smoothed_prior_ERA':round(r['prior_era'],3),
                'expected_starter_innings':round(r['projected_starter_innings'],2),
                'offense_runs_with_neutral_starter':round(r['neutral_regulation_runs'],3),
                'offense_runs_with_selected_starter':round(r['with_starter_regulation_runs'],3),
                'change_in_expected_runs':round(r['with_starter_regulation_runs']-r['neutral_regulation_runs'],3),
                'additional_correction_applied':r['starter_applied']})
        st.caption('The starter-vs-neutral calculation uses only the run model’s features; lineup/park/weather can still be unverified. The game outcome is never a model input.')
else:
    st.info('Starter comparison unavailable: '+str(starter_why.get('reason','Run an updated forecast.')))

st.markdown('<div class="v6-eyebrow">02 / Match prediction</div>',unsafe_allow_html=True)
if not pregame: st.warning('Historical replay only: this calculation was run after the scheduled start and does not prove what the model predicted before first pitch. Repeated scores can occur naturally. The game-day result is excluded from the scoring input.')
coverage=result.get('provenance',{}).get('pitcher_coverage',{})
gaps=result.get('data_gaps',[])
if gaps:
    st.caption(f"Data quality: starter history (away/home) {coverage.get('away',0)} / {coverage.get('home',0)} prior starts · {len(gaps)} unverified matchup input(s). Review in technical audit.")
else:
    st.caption('Data quality: listed matchup inputs were available; scenario coefficients still require prospective validation.')
line=st.number_input('Run-total threshold (runs)',min_value=.5,max_value=30.,value=7.5,step=.5,
                     help='Choose any run-total threshold to explore the simulated scoring distribution. At an integer threshold, exact totals are displayed separately.')
try:display=display_forecast(pred,match['away_name'],match['home_name'],line)
except (ValueError,KeyError) as exc:
    st.error(f'Cannot display an internally consistent V6 prediction: {exc}')
    st.stop()

away_name=clean_name(match['away_name']);home_name=clean_name(match['home_name'])
scoreline=f"{display['away_runs']}–{display['home_runs']}"
status='OFFICIAL GAME / PREGAME' if pregame else 'HISTORICAL REPLAY · NOT A SAVED PREGAME PICK'
status += (' · STARTERS INCLUDED (EXPERIMENTAL)' if all(impact_audit.get(side,{}).get('starter_applied') for side in ('home','away')) else ' · STARTER IMPACT NOT FULLY VERIFIED')
winner=clean_name(display['winning_team'])
st.markdown(f'''<div class="v6-hero">
<div class="v6-eyebrow">{status} · ONE SCORELINE</div>
<div class="v6-hero-title">{away_name} at {home_name}</div>
<div class="v6-board">
  <div class="v6-team"><small>AWAY</small><div class="v6-team-wrap"><span class="v6-team-mark">{team_mark(match["away"])}</span><span class="v6-team-word">{away_name}</span></div></div>
  <div class="v6-score">{display['away_runs']} <span style="color:#617b8b">:</span> {display['home_runs']}</div>
  <div class="v6-team right"><small>HOME</small><div class="v6-team-wrap"><span class="v6-team-mark">{team_mark(match["home"])}</span><span class="v6-team-word">{home_name}</span></div></div>
</div>
<div class="v6-total"><div><div class="v6-total-label">Scoreline total</div>
<strong>{display['total']} RUNS</strong></div>
<div style="text-align:right"><div class="v6-total-label">MODEL FAVORS</div>
<div style="font-size:1.08rem;color:#f4f7fa;font-weight:780">{winner} · {display['winner_probability']*100:.1f}%</div></div></div>
<div class="v6-sub-score">One plausible score near the simulation average; the mean can be fractional. Exact-score frequency: {display['chosen_score_probability']*100:.2f}%</div>
</div>''',unsafe_allow_html=True)

# The three baseball ratings are descriptive and game-date cutoff locked.
# The display cannot use the selected game's actual score or later dates.
strength=team_indices(historical_cutoff_assets(assets_cache(history_signature()),day)['enriched'],day,
                      match['away'],match['home'],data_dir=DATA)
away_idx=strength['teams'][match['away']]
home_idx=strength['teams'][match['home']]
def rating_card(name,data):
    def number(key):return str(data.get(key)) if data.get('available') and data.get(key) is not None else '—'
    def safe(s):return html.escape(str(s),quote=True)
    return (f'<div class="v6-rating-card"><div class="v6-rating-name">{safe(name)}</div>'
            f'<div class="v6-rating-body">'
            f'<div><small>Offense</small><div class="v6-rating-val">{number("offense")}</div></div>'
            f'<div><small>Defense</small><div class="v6-rating-val">{number("defense")}</div></div>'
            f'<div><small>Pitching</small><div class="v6-rating-val">{number("pitching")}</div></div>'
            f'</div></div>')
st.markdown('<div class="v6-section">Team strength · offense, defense & pitching</div>',unsafe_allow_html=True)
st.markdown('<div class="v6-ratings">'
    +rating_card(match['away_name'],away_idx)
    +rating_card(match['home_name'],home_idx)
    +'</div>',unsafe_allow_html=True)
st.markdown('<div class="v6-ratings-note">100 = historical MLB average; higher is better. '
  'Ratings summarize prior games ONLY and do not independently adjust the simulated forecast. '
  'Defense uses fielding-error proxy when available, otherwise a labeled runs-allowed proxy.</div>',unsafe_allow_html=True)
with st.expander('How offense, defense and pitching ratings are calculated',expanded=False):
    st.caption('Offense uses smoothed team runs scored. Defense is a rough fielding-error proxy (not Statcast OAA/DRS); if missing, runs allowed is shown and overlaps with pitching. Pitching uses combined starter + bullpen earned runs per inning from detailed prior-game CSV data. Ratings are descriptive, NOT new prediction inputs.')
    for code,data in ((match['away'],away_idx),(match['home'],home_idx)):
        st.write(f'**{TEAM_NAMES.get(code,code)}** · Previous team games: {data["games"]} · Fielding observations: {data["fielding_games"]} · Pitching box scores: {data["pitching_games"]}')
        st.caption('Defense: '+str(data['defense_source'])+' | Pitching: '+str(data['pitching_source']))

st.markdown('<div class="v6-section">Run-total probabilities</div>',unsafe_allow_html=True)
col_over,col_under=st.columns(2)
col_over.metric(f'Above {line:g} runs',f"{display['over']*100:.1f}%")
col_under.metric(f'Below {line:g} runs',f"{display['under']*100:.1f}%")
st.markdown(f'<div class="v6-bar"><div class="v6-over" style="width:{display["over"]*100:.3f}%"></div><div class="v6-under" style="width:{display["under"]*100:.3f}%"></div></div>',unsafe_allow_html=True)
if display['push']>1e-8:st.caption(f"Exactly {line:g} runs: {display['push']*100:.1f}% of simulated games finish on the threshold.")
if display['over']>display['under']+.06:lean=f'More simulated games finish above {line:g} runs'
elif display['under']>display['over']+.06:lean=f'More simulated games finish below {line:g} runs'
else:lean='Neither side dominates at this run threshold'
st.markdown(f'<div class="v6-lean">◉ &nbsp; {lean} &nbsp; · &nbsp; <span style="color:#99bdb3">Research estimate only · review model uncertainty</span></div>',unsafe_allow_html=True)

# Direct visual counterpart of the soccer video's probability heatmap:
# Each square is calculated from the SAME Monte Carlo draws as the total and winner.
st.markdown('<div class="v6-section">Score probability map</div>',unsafe_allow_html=True)
with st.expander('Open the score-probability heatmap',expanded=False):
    st.caption('Simulated FINAL scores, including extra innings. Rows = home runs; columns = away runs. '
               'Unlike the TikTok, a single MLB exact score is not assigned the overall winner probability.')
    st.markdown(heatmap_html(pred['score_grid'],match['away_name'],match['home_name'],
             highlight=(display['home_runs'],display['away_runs'])),unsafe_allow_html=True)
    st.markdown(f'<div class="v6-exact-note">Displayed score frequency: '
                f'<span class="v6-keypoint">{100*display["chosen_score_probability"]:.2f}%</span> · '
                f'Overall {winner} win chance: '
                f'<span class="v6-keypoint">{100*display["winner_probability"]:.1f}%</span> · '
                f'{pred["simulation_size"]:,} simulated games.</div>',unsafe_allow_html=True)

with st.expander('How the numbers work · model quality · technical audit',expanded=False):
    st.markdown('**Why scores can repeat:** The simulator uses a reproducible game-specific random seed. Two different games can naturally produce the same representative score. We do not change a prediction just because a game has already happened. The displayed score is near the rounded mean total; it is not the actual result, nor guaranteed to differ from it.')
    st.markdown('**Historical replay integrity:** The simulation receives only completed games strictly BEFORE the selected game date. The 2023–24 training fit is frozen. Pregame evidence that was not archived before the start (e.g., confirmed lineup) is not retrospectively certified. A replay produced after first pitch is **not** a genuine logged pregame pick.')
    if not pregame:st.caption('Historical starting pitchers: '+('Retrospective schedule-listed scenario — may contain knowledge gained after first pitch' if use_historical_starters else 'Excluded unless independently documented before first pitch'))
    st.caption(f"Cutoff (exclusive): {day.isoformat()} · Model version: {result.get('model_version')} · Simulation seed: {result.get('simulation',{}).get('seed','unavailable')}")
    st.metric('Mean combined runs across ALL simulations',f"{display['model_mean_total']:.2f}")
    c1,c2=st.columns(2)
    c1.metric(f"Mean {match['away_name']} runs",f"{pred['away_expected_runs']:.2f}")
    c2.metric(f"Mean {match['home_name']} runs",f"{pred['home_expected_runs']:.2f}")
    st.caption(f"Scoreline occurrence: {display['chosen_score_probability']*100:.2f}% in this simulation; 80% total range: {pred['total_80_range'][0]}–{pred['total_80_range'][1]}.  The ±{pred['monte_carlo_95_half_width_pp']:.2f} pp Monte Carlo error is only sampling uncertainty, not model uncertainty.")
    st.markdown('**Data availability**')
    st.dataframe(data_readiness(result),hide_index=True,use_container_width=True)
    for gap in result.get('data_gaps',[]):st.caption('• '+str(gap))
    st.caption('2025 and 2026 games have already influenced prior model design. Lineup, park and weather scenario effects remain incompletely validated; use future games to measure forecast performance.')
    st.json({'core_training':result.get('training'),
             'baseline':result.get('baseline'),
             'adjustments':result.get('adjustments'),
             'simulation':result.get('simulation'),
             'data_provenance':result.get('provenance')},expanded=False)

st.caption('MLB Forecast Lab · Baseball-only statistical research. Forecasts describe uncertainty; they do not guarantee future game outcomes.')
