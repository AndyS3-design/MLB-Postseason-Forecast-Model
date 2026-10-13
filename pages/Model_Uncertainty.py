"""Streamlit page for independently saved robust_validation_2026 results."""
from pathlib import Path
import json
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
st.set_page_config(page_title='Model Uncertainty | MLB Prediction Lab',page_icon='📉',layout='wide')
st.title('📉 Model comparison & predictive uncertainty')
st.caption('Chronological retrospective evaluation · Identical game IDs · No automated picks or trades')

season=st.selectbox('Evaluation year',[2026,2025],index=0)
path=ROOT/'outputs'/f'robust_validation_{season}.json'
if not path.exists():
    st.info(f'Run `py robust_score_validation.py --target-year {season} --as-of '
            + ('2026-10-12' if season==2026 else '2026-01-01')
            + '` in Developer PowerShell, then refresh this page.')
    st.stop()
try:
    result=json.loads(path.read_text(encoding='utf-8'))
except (OSError,ValueError) as exc:
    st.error(f'Unable to load model report: {exc}');st.stop()
if result.get('status')!='COMPLETED':
    st.warning('No completed validation data in this report');st.json(result);st.stop()
if result.get('partial_test_mode'):
    st.error('This file contains only a partial diagnostic sample, not a full-season backtest.');st.stop()

st.write(f"Training seasons: **{result.get('training_years')}** · "
         f"Data cutoff: **{result.get('cutoff_exclusive')} (exclusive)**")
st.warning('The model and candidate families have been reviewed using past 2025/2026 outcomes during development. '
           'This is retrospective validation, not a pristine untouched holdout or evidence of profitable Kalshi trading.')

split=st.radio('Compare games',['Regular season','Postseason','All available'],horizontal=True)
key={'Regular season':'regular','Postseason':'postseason','All available':'all'}[split]
summary=result['splits'].get(key,{})
if not summary.get('n'):
    st.info('No games in this group.');st.stop()
st.subheader(f'{split}: {summary["n"]:,} games')
if key=='postseason':st.warning('Postseason sample is too small for confident model selection.')

winner=summary.get('winner_models',{})
if winner:
    st.markdown('### Winner models (same games)')
    st.dataframe(pd.DataFrame([{'Model':k,'Brier score ↓':v['brier'],'Winner accuracy ↑':v['accuracy'],
                               'Both starters observed':v.get('both_starters_have_prior_detail','—')}
                              for k,v in winner.items()]).style.format({'Brier score ↓':'{:.5f}',
                              'Winner accuracy ↑':'{:.2%}'}),hide_index=True,use_container_width=True)
    ci=summary.get('winner_brier_expanded_minus_elo_ci_95')
    if ci:st.caption(f'95% game-day bootstrap interval, expanded minus Elo winner Brier: '
                     f'{ci[0]:+.5f} to {ci[1]:+.5f}. Negative means expanded is better.')
    st.caption('Poisson/NB final-score models are ALL aligned to the same Elo winner probability; '
               'they cannot be compared as separate winner models.')

st.markdown('### Final-score distributions')
names={'poisson':'Poisson','validated_nb':'Validated-dispersion NB',
       'wide_nb':'Wider NB (1.5× dispersion)','constant_nb':'Constant-run baseline'}
vals=summary.get('models',{})
rows=[]
for k,v in vals.items():
    rows.append({'Scoring method':names.get(k,k),'Total runs CRPS ↓':v.get('total_crps'),
                 'Team runs CRPS ↓':v.get('team_runs_crps'),
                 'Exact score log loss ↓':v.get('exact_log_loss'),
                 'Under 6.5 Brier ↓':v.get('under_brier'),
                 '80% total-run interval coverage':v.get('pi80_total_coverage'),
                 '80% interval width (runs)':v.get('pi80_total_width')})
if rows:
    st.dataframe(pd.DataFrame(rows).style.format({
        'Total runs CRPS ↓':'{:.4f}','Team runs CRPS ↓':'{:.4f}',
        'Exact score log loss ↓':'{:.4f}','Under 6.5 Brier ↓':'{:.4f}',
        '80% total-run interval coverage':'{:.1%}',
        '80% interval width (runs)':'{:.2f}'
    }),hide_index=True,use_container_width=True)
    st.caption('Discrete CRPS is a proper scoring rule for the ENTIRE run-total distribution. '
               'Lower is better. A nominal 80% predictive interval should contain roughly 80% of results, '
               'but discreteness makes overcoverage normal.')

st.markdown('### Day-cluster uncertainty intervals')
ci_rows=[]
for name,all_ci in summary.get('paired_95pct_ci_delta_vs_validated_nb',{}).items():
    for metric,interval in all_ci.items():
        ci_rows.append({'Alternative':names.get(name,name),'Metric':metric,
                        '95% lower':interval[0] if interval else None,
                        '95% upper':interval[1] if interval else None})
if ci_rows:
    st.dataframe(pd.DataFrame(ci_rows),hide_index=True,use_container_width=True)
    st.caption('Intervals are (alternative − validated-dispersion NB). An interval crossing 0 is inconclusive. '
               'Resampling covers dates, not possible model-specification error.')

with st.expander('Methodology, caveats, and reproducibility'):
    for key,item in result.get('candidate_definitions',{}).items():
        st.write(f'**{names.get(key,key)}:** {item}')
    for item in result.get('limitations',[]):st.write('• '+item)
    st.write('All scores are final scores; the extra-inning simulation remains approximate.')

games=ROOT/'outputs'/f'robust_validation_{season}_games.csv'
if games.exists():
    st.download_button('Download per-game comparison CSV', games.read_bytes(),
                       file_name=games.name,mime='text/csv')
st.info('No model is automatically promoted. A separately collected, future prospective test and timestamped '
        'transaction prices are required before making any profitability claim.')
