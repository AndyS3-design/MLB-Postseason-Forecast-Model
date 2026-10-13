"""Local Streamlit frontend for historical MLB research and manual quote analysis.
Run: py -m streamlit run dashboard.py
"""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from extended_eval import all_games
from matchup_model import backtest_expanded, expanded_forecast, resolve_starter
from forecast_engine import (TEAM_NAMES, build_run_fit, fetch_schedule, forecast,
                             historical_snapshot, quote_analysis)
from market_backtest import analyze as analyze_historical_quotes
from data_refresh import refresh as refresh_mlb_data, refreshed_today
from score_projection import project_score

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'

st.set_page_config(page_title='MLB Prediction Lab',page_icon='⚾',layout='wide')
st.markdown('''<style>
  .block-container {max-width: 1250px; padding-top: 1.5rem;}
  .subtle {color:#91a3b9; font-size:0.85rem}
  .stMetric {border:1px solid rgba(120,150,175,.22); padding:12px; border-radius:12px}
</style>''',unsafe_allow_html=True)
st.title('⚾ MLB Prediction Lab')
st.caption('Research dashboard · tested Elo baseline + expanded matchup prototype · exploratory totals · manual quotes')


def file_signature():
    names=['GL2023.TXT','GL2024.TXT','GL2025.TXT',
           'mlb_2026_regular.csv','mlb_postseason_2023_2026.csv',
           'advanced_pitching_details.csv','pitcher_directory.csv']
    return tuple((p.name,p.stat().st_mtime_ns,p.stat().st_size)
                 for p in (DATA/n for n in names) if p.exists())


@st.cache_data(show_spinner='Loading completed MLB games…')
def read_history(signature):
    return all_games(DATA,True)


@st.cache_resource(show_spinner='Fitting experimental run model on 2023–2024 data…')
def read_run_fit(signature):
    return build_run_fit(DATA)


@st.cache_resource(show_spinner='Evaluating expanded matchup model on held-out seasons…')
def read_expanded_fit(signature):
    return backtest_expanded(read_history(signature),DATA,ROOT/'outputs')


@st.cache_data(ttl=300,show_spinner='Checking MLB schedule…')
def read_schedule(day_string):
    return fetch_schedule(date.fromisoformat(day_string))



def fmt_eastern(utc):
    if not utc:return 'Time unavailable'
    try:
        dt=datetime.fromisoformat(str(utc).replace('Z','+00:00'))
        return dt.astimezone(ZoneInfo('America/New_York')).strftime('%I:%M %p ET')
    except (TypeError,ValueError):return str(utc)


with st.sidebar:
    st.header('Settings')
    game_day=st.date_input('Game date',value=date.today(),
                          min_value=date(2023,1,1),max_value=date(2026,12,31))
    st.caption('Prediction cutoff: games played before this date only. Never uses same-day scores.')
    include_totals=st.toggle('Show experimental run totals',value=True)
    st.divider()
    st.subheader('Data')
    st.caption('Bundled: 2023–2025 Retrosheet logs. Your 2026 results and optional detailed pitching statistics remain in this folder.')
    auto_refresh=st.toggle('Auto-refresh on first visit each day',value=True,
         help='Runs on dashboard opening only; this does not install a background scheduler.')
    manually_refresh=st.button('Refresh 2026 completed results now',use_container_width=True)
    today=date.today()
    due=(auto_refresh and today.year==2026 and
         not refreshed_today(ROOT,today) and
         st.session_state.get('daily_attempt')!=today.isoformat())
    if manually_refresh or due:
        st.session_state['daily_attempt']=today.isoformat()
        if today.year!=2026:
            st.warning('The provided importer currently supports 2026 games only.')
        else:
            try:
                with st.spinner('Refreshing MLB results through yesterday (may take a minute)…'):
                    refresh_result=refresh_mlb_data(ROOT,today,force_latest_month=True)
                st.success(f"Data current through {today-timedelta(days=1)}: {refresh_result['result']['2026_regular_games']} regular-season records.")
                read_history.clear()
            except Exception as exc:
                st.warning(f'Automatic refresh could not complete; previous data retained. {exc}')
    st.caption('Updates run while the dashboard is open, not continuously in the background. Previously imported data is restored if a refresh fails.')
    if st.button('Clear dashboard caches',use_container_width=True):
        read_history.clear();read_schedule.clear();read_expanded_fit.clear();st.success('Caches cleared.')
    st.divider()
    st.caption('Neither Kalshi nor an automated broker is connected. No transactions are placed.')


try:
    sig=file_signature()
    games=read_history(sig)
except (FileNotFoundError,ValueError) as exc:
    st.error(f'Game logs could not be read: {exc}')
    st.info('Keep the dashboard files in your current backtest folder, alongside `backtest.py` and `data/`.')
    st.stop()

snapshot=historical_snapshot(games,game_day)
season_games=sum(int(g['year']==game_day.year) for g in snapshot)
last_day=max((pd.Timestamp(g['date']).date() for g in snapshot),default=None)
cols=st.columns(3)
cols[0].metric('Completed games in model history',f'{len(snapshot):,}')
cols[1].metric(f'{game_day.year} games available',f'{season_games:,}')
cols[2].metric('Latest included game',last_day.strftime('%b %d, %Y') if last_day else 'None')

if game_day.year==2026 and season_games==0:
    st.warning('No 2026 games are available in this copy yet. Copy your existing `data/mlb_2026_regular.csv` and postseason CSV into this folder, or use Refresh 2026 completed results.')
if game_day.year==2026 and last_day and (game_day-last_day).days>14:
    st.warning('The latest imported result is over two weeks old. This forecast may be stale; refresh MLB results.')

schedule_tab,prices_tab,validation_tab=st.tabs(['🎯 Game forecasts','💲 Kalshi price check','📈 Backtest & data quality'])

with schedule_tab:
    st.subheader('Choose a matchup')
    source=st.radio('Matchup source',['Today’s MLB schedule','Manual team selection'],horizontal=True)
    match=None
    if source=='Today’s MLB schedule':
        try:
            choices=read_schedule(game_day.isoformat())
            if choices:
                labels=[f"{g['away_name']} at {g['home_name']} · {fmt_eastern(g['start_utc'])} · {g['status']}" for g in choices]
                choice=st.selectbox('Official schedule',range(len(labels)),format_func=lambda i:labels[i])
                match=choices[choice]
                st.caption(f"Probable pitchers: {match['away_name']}: {match['away_pitcher']} · {match['home_name']}: {match['home_pitcher']}")
                st.caption(f"Game state: {match['status']}. Predictions are always pregame, not live/in-game forecasts.")
            else:
                st.info('No MLB games found for this date. Try manual selection.')
        except Exception as exc:
            st.warning(f'Could not load MLB schedule: {exc}. Use manual team selection instead.')
    else:
        cl,cr=st.columns(2)
        codes=sorted(TEAM_NAMES, key=lambda c:TEAM_NAMES[c])
        home=cl.selectbox('Home team',codes,format_func=lambda c:TEAM_NAMES[c],index=codes.index('MIL'))
        away=cr.selectbox('Away team',codes,format_func=lambda c:TEAM_NAMES[c],index=codes.index('LAN'))
        if home==away:
            st.error('Please choose two different teams.')
        else:match={'home':home,'away':away,'home_name':TEAM_NAMES[home],
                    'away_name':TEAM_NAMES[away], 'game_type':'manual','status':'Not verified'}

    if match:
        with st.spinner('Computing pregame probabilities…'):
            try:
                fit=read_run_fit(sig) if include_totals else None
                pred=forecast(games,game_day,match['home'],match['away'],fit)
                st.session_state['forecast']=pred
                st.session_state['match_desc']=f"{match['away_name']} at {match['home_name']}"
            except Exception as exc:
                st.error(f'Forecast unavailable: {exc}')
                pred=None
        if pred is not None:
            st.subheader(st.session_state['match_desc'])
            pcols=st.columns(2)
            pcols[0].metric(f"{match['away_name']} win",f"{pred['away_win_probability']:.1%}")
            pcols[1].metric(f"{match['home_name']} win",f"{pred['home_win_probability']:.1%}")
            st.progress(float(pred['home_win_probability']),text='Home-team Elo win probability')
            if 'under_6_5_probability' in pred:
                tcols=st.columns(3)
                tcols[0].metric('Expected combined runs (regulation)',f"{pred['combined_runs_regulation']:.1f}")
                tcols[1].metric('Under 6.5 (incl. extras estimate)',f"{pred['under_6_5_probability']:.1%}")
                tcols[2].metric('Over 6.5',f"{pred['over_6_5_probability']:.1%}")
                st.warning('The run-total model has NOT demonstrated a dependable edge in historical holdouts. These totals are exploratory, not backtest-calibrated betting advice.')
                with st.expander('🎯 Projected final score — experimental', expanded=True):
                    # Uses 2023–24-trained run model, then aligns winning side
                    # to the better-tested Elo winner probability; never a
                    # single exact-score guarantee or a live betting signal.
                    try:
                        _,_,alpha_h,alpha_a,extra_fit=fit
                        proj=project_score(pred['home_runs_regulation'],pred['away_runs_regulation'],
                                           alpha_h,alpha_a,extra_fit,pred['home_win_probability'])
                        favored_home=pred['home_win_probability']>=.5
                        pick=proj['representative_favorite_score']
                        st.markdown(f"**Projected winning score:** {match['away_name']} **{pick['away_runs']}** – {match['home_name']} **{pick['home_runs']}**")
                        st.caption(f"This particular exact score has an estimated {pick['probability']:.1%} chance in the EXPERIMENTAL score distribution. The model favors {'home' if favored_home else 'away'} team based on Elo, not on the score model alone.")
                        q1,q2,q3=st.columns(3)
                        q1.metric(f"{match['home_name']} expected final runs",f"{proj['expected_home_final']:.2f}")
                        q2.metric(f"{match['away_name']} expected final runs",f"{proj['expected_away_final']:.2f}")
                        q3.metric('Elo-aligned home win',f"{proj['home_win_probability']:.1%}")
                        top=pd.DataFrame([{
                            'Final score':f"{match['away_name']} {z['away_runs']} – {match['home_name']} {z['home_runs']}",
                            'Probability':f"{z['probability']:.2%}"} for z in proj['top_scores']])
                        st.dataframe(top,hide_index=True,use_container_width=True)
                        if abs(proj['raw_run_model_home_win']-pred['home_win_probability'])>.12:
                            st.warning('Run-score model and Elo disagree substantially. Scores were adjusted to Elo while holding total-run chances fixed; this does NOT validate either run prediction.')
                        st.warning('Exact scores are highly uncertain. Extra innings are approximated, and historical testing has not established reliable score accuracy or positive trading returns.')
                        st.session_state['score_forecast']=proj
                    except Exception as err:
                        st.warning(f'Experimental score projection unavailable: {err}')
                if abs(float(pred['home_win_run_model'])-float(pred['home_win_probability']))>.15:
                    st.warning('Model disagreement: the experimental run-based winner estimate differs from Elo by more than 15 percentage points. The run model has weaker holdout validation and should not override the Elo baseline.')
            st.caption('Primary win probabilities remain the **Elo baseline** (K=8, home advantage 20 rating points, offseason carryover 0.75). The expanded matchup research model below is separate. Neither model has an injury feed or verified lineup adjustment.')
            with st.expander('⚾ Expanded matchup model — research comparison',expanded=True):
                try:
                    advanced,model,frame,hands,directory=read_expanded_fit(sig)
                    st.caption('Uses lagged starter performance, offense, bullpen workload, rest and managerial usage proxies. **Not promoted** unless holdouts show robust improvement over Elo.')
                    hname=match.get('home_pitcher','')
                    aname=match.get('away_pitcher','')
                    hp=match.get('home_pitcher_id') or resolve_starter(hname,directory)
                    ap=match.get('away_pitcher_id') or resolve_starter(aname,directory)
                    ca,cb=st.columns(2)
                    hp=ca.text_input('Home starting pitcher ID (optional)',value=hp or '',help='Use MLB-12345 for imported 2026 MLB boxscores, or Retrosheet ID from pitcher_directory.csv. Unknown IDs have NO performance effect.')
                    ap=cb.text_input('Away starting pitcher ID (optional)',value=ap or '',help='Do not guess an ID; leave blank if unknown.')
                    ext=expanded_forecast(games,game_day,match['home'],match['away'],model,hands,hp,ap,data_dir=DATA)
                    x1,x2,x3=st.columns(3)
                    x1.metric('Elo baseline — home win',f"{pred['home_win_probability']:.1%}")
                    x2.metric('Expanded research — home win',f"{ext['p_home_expanded']:.1%}")
                    x3.metric('Model disagreement',f"{(ext['p_home_expanded']-pred['home_win_probability'])*100:+.1f} pp")
                    b1,b2=st.columns(2)
                    b1.metric('Home starter prior detailed starts',ext['home_sp_era_observed'])
                    b2.metric('Away starter prior detailed starts',ext['away_sp_era_observed'])
                    if not(ext['home_sp_era_observed'] and ext['away_sp_era_observed']):
                        st.warning('Starter-specific ERA/strikeout features are NOT fully available for this matchup. Import detailed historical pitching data before interpreting pitcher adjustments.')
                    st.caption(f"Reliever appearances used in prior 3 days: home {ext['home_bp_used_last3']:.0f} / away {ext['away_bp_used_last3']:.0f}. This is a rough fatigue proxy, not a reliever-by-reliever workload model.")
                    baseline=advanced['splits'].get('2025_regular',{})
                    if baseline.get('n'):
                        delta=baseline['elo']['brier']-baseline['expanded']['brier']
                        st.caption(f"2025 independent holdout: Elo Brier {baseline['elo']['brier']:.4f}; expanded Brier {baseline['expanded']['brier']:.4f}; improvement {delta:+.5f} (positive means expanded was better).")
                    with st.expander('Expanded model feature audit'):
                        st.json(ext)
                    st.session_state['expanded_forecast']=ext
                except Exception as exc:
                    st.warning(f'Expanded model could not run: {exc}. Elo baseline remains available.')
            with st.expander('Prediction audit trail'):
                st.json({k:(v.isoformat() if isinstance(v,date) else v) for k,v in pred.items()})
                st.caption('Every included historical game date is strictly earlier than the selected forecast date. Same-day scores are excluded—even when the schedule already shows a final score.')

with prices_tab:
    st.subheader('Compare a manually entered executable YES ask')
    pred=st.session_state.get('forecast')
    if pred is None or pred.get('date')!=game_day.isoformat():
        st.info('Select a matchup under Game forecasts to enable contract analysis.')
    else:
        desc=st.session_state.get('match_desc',f"{pred['away']} at {pred['home']}")
        st.write(f'**Forecast:** {desc} · {pred["date"]}')
        options={
          f"{TEAM_NAMES[pred['home']]} wins":pred['home_win_probability'],
          f"{TEAM_NAMES[pred['away']]} wins":pred['away_win_probability']}
        if 'under_6_5_probability' in pred:
            options['Under 6.5 total runs']=pred['under_6_5_probability']
            options['Over 6.5 total runs']=pred['over_6_5_probability']
        market=st.selectbox('Contract',list(options))
        probability=options[market]
        st.write(f'Model YES probability: **{probability:.1%}**')
        ask_str=st.text_input('Your actual executable YES ask (cents per $1 contract)',
             value='',placeholder='e.g. 55 — leave blank until you look up the quote')
        fee_str=st.text_input('Estimated Kalshi fee (cents per contract)',
             value='',placeholder='e.g. 1 — enter the applicable fee')
        if ask_str.strip() and fee_str.strip():
            try:
                info=quote_analysis(probability,float(ask_str),float(fee_str))
                ca,cb,cc=st.columns(3)
                ca.metric('Break-even probability',f"{info['break_even_probability']:.1%}")
                cb.metric('Modeled edge',f"{info['edge_pp']:+.1f} pp")
                cc.metric('Expected result / $1 contract',f"${info['expected_value_usd_per_contract']:+.3f}")
                st.caption(f"If YES wins, net per contract: ${info['win_profit_usd']:+.2f}; if it loses: ${info['loss_usd']:.2f}.")
                if info['edge_pp']>=5:
                    st.warning('Possible modeled price discrepancy. Not a verified trading edge: calibration, quote freshness, liquidity, and fees still matter.')
                else:
                    st.info('No robust pricing advantage established. Small differences can be model noise.')
            except ValueError as exc:st.error(f'Invalid price or fee: {exc}')
        st.caption('This tool neither reads Kalshi live quotes nor guarantees fills. A chart price, payout multiplier, or portfolio valuation is not an executable sell/buy quote.')

with validation_tab:
    st.subheader('Historical evidence')
    metrics_path=ROOT/'outputs'/'extended_metrics.json'
    if metrics_path.exists():
        try:
            results=json.loads(metrics_path.read_text())
            splits=results.get('splits',{})
            rows=[]
            for name,v in splits.items():
                if not isinstance(v,dict) or not v.get('n'):continue
                ew=v.get('elo_winner',{})
                rows.append({'Split':name,'Games':int(v['n']),
                             'Elo winner accuracy':f"{ew['accuracy']:.1%}" if 'accuracy' in ew else '—',
                             'Elo Brier':round(ew['brier'],4) if 'brier' in ew else None})
            if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            else:st.info('No evaluated splits in metrics JSON.')
        except (ValueError,KeyError,TypeError) as exc:st.warning(f'Unable to read stored metrics: {exc}')
    else:st.info('Run `py run_all.py` to generate the historical results here.')
    st.warning('Backtest performance can change if earlier historical data are added, even though later outcomes must not affect earlier forecasts. All rates are observational; no positive expected return is established.')
    score_path=ROOT/'outputs'/'score_metrics_2025.json'
    st.markdown('#### Exact final-score holdout (2025 regular season)')
    if score_path.exists():
        try:
            report=json.loads(score_path.read_text())
            st.dataframe(pd.DataFrame([
                {'Metric':'Absolute final runs error per team (lower better)',
                 'Experimental score model':round(report['mean_run_absolute_error_per_team']['score_model'],3),
                 'Constant-run baseline':round(report['mean_run_absolute_error_per_team']['constant_team_run_baseline'],3)},
                {'Metric':'Exact-score top-pick hit rate (higher better)',
                 'Experimental score model':round(report['most_likely_exact_score_hit_rate']['score_model'],4),
                 'Constant-run baseline':round(report['most_likely_exact_score_hit_rate']['constant_team_run_baseline'],4)},
                {'Metric':'Exact-score log loss (lower better)',
                 'Experimental score model':round(report['exact_score_log_loss']['score_model'],3),
                 'Constant-run baseline':round(report['exact_score_log_loss']['constant_team_run_baseline'],3)},
                {'Metric':'Under 6.5 Brier score (lower better)',
                 'Experimental score model':round(report['under_6_5_brier']['score_model'],4),
                 'Constant-run baseline':round(report['under_6_5_brier']['constant_team_run_baseline'],4)},
            ]),hide_index=True,use_container_width=True)
            st.caption(f"Score evaluation: {report['n']:,} 2025 regular-season games, 2023–24 training. Extra innings simplified; same 2025 season previously informed model development.")
        except Exception as exc:
            st.warning(f'Cannot read score evaluation: {exc}')
    else:
        st.info('Run `py score_backtest.py` to calculate genuine 2025 score accuracy and compare against a simple baseline.')
    st.markdown('#### Historical Kalshi quote audit (optional)')
    st.caption('Upload real, timestamped, executable quote CSV with the exact schema in `examples/historical_kalshi_quotes_TEMPLATE.csv`. The tool rejects post-first-pitch and indicative quotes.')
    upl=st.file_uploader('Historical Kalshi quotes (.csv)',type=['csv'])
    if upl:
        pred_path=ROOT/'outputs'/'extended_predictions.csv'
        if not pred_path.exists():st.error('Run `py run_all.py` first to create `outputs/extended_predictions.csv`.')
        else:
            try:
                quote_df=pd.read_csv(upl,dtype={'game_id':str})
                hist_preds=pd.read_csv(pred_path,dtype={'game_id':str})
                summary,trade_rows=analyze_historical_quotes(hist_preds,quote_df)
                st.json(summary)
                if len(trade_rows):st.dataframe(trade_rows,hide_index=True)
            except Exception as exc:st.error(f'Historical quote audit rejected input: {exc}')
    st.markdown('#### Expanded matchup model holdout')
    try:
        advanced,_,_,_,_=read_expanded_fit(sig)
        rows=[]
        for name,split in advanced['splits'].items():
            if not split.get('n'):continue
            rows.append({'Holdout':name,'Games':split['n'],
              'Elo Brier':round(split['elo']['brier'],5),
              'Expanded Brier':round(split['expanded']['brier'],5),
              'Difference (Elo minus expanded)':round(split['elo']['brier']-split['expanded']['brier'],5),
              'Detailed starter coverage':f"{split['starter_observed_games']}/{split['n']}"})
        if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
        st.caption(f"Historical actual pitching boxscore rows: {advanced['details_rows_applied']:,}. Known pitcher throwing hands: {advanced['handed_pitchers']:,}. Adding richer features does not by itself establish improved predictions.")
    except Exception as exc:st.warning(f'Expanded model validation unavailable: {exc}')
    st.caption('Regular-season data copyright Retrosheet. Official MLB API provides schedule and game records; market prices are user-supplied only.')
