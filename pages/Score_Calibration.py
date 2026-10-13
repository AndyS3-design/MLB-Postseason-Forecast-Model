"""Streamlit multipage research viewer for score_calibration_2026.py output.

The page never generates odds or places trades; it reads saved evaluations.
"""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
METRICS=ROOT/'outputs'/'score_calibration_2026.json'
GAMES=ROOT/'outputs'/'score_calibration_2026_games.csv'

st.set_page_config(page_title='MLB Score Calibration',page_icon='📊',layout='wide')
st.title('📊 Exact-score calibration — 2026')
st.caption('Historical out-of-sample score evaluation, not predictions or betting advice')
if not METRICS.exists():
    st.info('Run `py score_calibration_2026.py --as-of 2026-10-12` in Visual Studio first. ' 
            'Then refresh this page. It uses your existing 2026 game files.')
    st.stop()
try:
    r=json.loads(METRICS.read_text())
except Exception as e:
    st.error(f'Unable to parse saved score calibration report: {e}')
    st.stop()
if r.get('status')!='COMPLETED':
    st.warning('2026 evaluation unavailable — import completed 2026 scores and rerun the script.')
    st.json(r)
    st.stop()
st.write(f"**Test season:** {r['target_year']} · **Exclusive cutoff:** {r['cutoff_exclusive']} · "
         f"**Frozen training:** {', '.join(map(str,r['training_seasons']))}")

for label,key in [('2026 Regular season','regular_2026_or_requested_year'),
                  ('2026 Postseason','postseason_2026_or_requested_year'),
                  ('2026 Combined','combined')]:
    split=r.get(key,{})
    st.subheader(label)
    if not split.get('n'):
        st.info('No games available for this split.');continue
    n=split['n']
    st.caption(f'{n:,} games · A small postseason sample is not sufficient for strong conclusions.')
    def measure(name,kind):
        return split[name][kind]
    comparison=pd.DataFrame([
        {'Metric':'Final-score runs MAE / team (lower better)',
            'Experimental model':measure('mean_absolute_error_per_team','score_model'),
            'Constant-runs baseline':measure('mean_absolute_error_per_team','constant_runs_baseline')},
        {'Metric':'Exact-score top-pick accuracy (higher better)',
            'Experimental model':measure('top_score_correct','score_model'),
            'Constant-runs baseline':measure('top_score_correct','constant_runs_baseline')},
        {'Metric':'Exact-score log loss (lower better)',
            'Experimental model':measure('exact_score_log_loss','score_model'),
            'Constant-runs baseline':measure('exact_score_log_loss','constant_runs_baseline')},
        {'Metric':'Under 6.5 Brier score (lower better)',
            'Experimental model':measure('under_6_5_brier','score_model'),
            'Constant-runs baseline':measure('under_6_5_brier','constant_runs_baseline')},
    ])
    st.dataframe(comparison.round(5),hide_index=True,use_container_width=True)
    pred=split.get('overall_top_pick_predicted_probability')
    actual=split.get('overall_top_pick_actual_hit_rate')
    if pred is not None:
        c1,c2=st.columns(2)
        c1.metric('Mean forecast chance of most likely score',f'{pred:.2%}')
        c2.metric('Most likely score actually occurred',f'{actual:.2%}')
    display_pred=split.get('overall_displayed_score_predicted_probability')
    if display_pred is not None:
        a,b=st.columns(2)
        a.metric('Mean probability of displayed winning score',f'{display_pred:.2%}')
        b.metric('Displayed winning score actually occurred',f"{split['overall_displayed_score_actual_hit_rate']:.2%}")
    bins=split.get('displayed_winning_score_calibration',[])
    if bins:
        st.markdown('**Reliability of the dashboard’s displayed favorite-winning score**')
        table=pd.DataFrame([{
            'Predicted probability bin':item['range'],'Games':item['games'],
            'Mean predicted':item['mean_predicted_probability'],
            'Observed hit rate':item['observed_frequency'],
            '95% observed lower':item['observed_95pct_wilson'][0],
            '95% observed upper':item['observed_95pct_wilson'][1],
        } for item in bins])
        st.dataframe(table.style.format({col:'{:.2%}' for col in
            ['Mean predicted','Observed hit rate','95% observed lower','95% observed upper']}),
            hide_index=True,use_container_width=True)
        st.caption('These bins check the displayed favored-winning score (not every score cell); the model also reports top-score calibration in JSON.')

with st.expander('Model uncertainty and limitations'):
    st.write('**95% paired bootstrap intervals, model minus baseline:**')
    st.json(r.get('day_cluster_bootstrap_95pct_delta_model_minus_baseline',{}))
    for item in r.get('limitations',[]):st.write('• '+item)
if GAMES.exists():
    st.download_button('Download game-level 2026 forecast audit (CSV)',
       GAMES.read_bytes(),file_name=GAMES.name,mime='text/csv')

st.warning('An exact score is highly unlikely even for the most probable outcome. '
 'No profit advantage has been validated; forecasts use simplified extra innings and an Elo adjustment.')
