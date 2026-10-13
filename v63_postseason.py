"""Time-aware postseason scoring context, a deliberately conservative scenario.

Season rows: user supplied. The 2022-26 regular/postseason runs/team-game
series is independently corroborated by CBS Sports (published Oct 11, 2026).
Other annual aggregate columns are user supplied and NOT independently audited.

No 2026 postseason aggregate is available to a historical forecast before
2026-10-12; similarly, no completed season can enter its own past forecasts.
This contextual prior is NOT an independently backtested betting model.
"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import csv,math

COLS=('Year','Reg_Runs_Per_Game','Post_Runs_Per_Game',
 'Reg_Reliever_IP_Pct','Post_Reliever_IP_Pct','Reg_HR_Per_Game','Post_HR_Per_Game',
 'Reg_Runs_Via_HR_Pct','Post_Runs_Via_HR_Pct',
 'Reg_Avg_Fastball_MPH','Post_Avg_Fastball_MPH')
# Same rates available in an October 11, 2026 published report BEFORE 2026 NLCS.
# Conservative start-date gate rather than trusting same-day intraday ordering.
FIRST_2026_SNAPSHOT_DATE=date(2026,10,12)
# Explicit, sensitivity-tested judgment weights, NOT statistically fitted.
CURRENT_SEASON_BLEND=.30
CONTEXT_STRENGTH=.80  # retain 20% of underlying team prediction
DEFAULT_DATA=Path(__file__).resolve().parent/'data'/'postseason_context_2022_2026.csv'


def load_years(path=DEFAULT_DATA):
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if tuple(reader.fieldnames or ())!=COLS:
            raise ValueError('Unexpected postseason context CSV schema')
        items=[]
        for row in reader:
            entry={'Year':int(row['Year'])}
            for col in COLS[1:]:
                v=float(row[col]);
                if not math.isfinite(v) or v<=0:raise ValueError(f'Invalid value in {col}')
                entry[col]=v
            if not 20<entry['Reg_Reliever_IP_Pct']<80 or not 20<entry['Post_Reliever_IP_Pct']<80:
                raise ValueError('Unreasonable reliever share')
            items.append(entry)
    yrs=[r['Year'] for r in items]
    if yrs!=sorted(set(yrs)) or len(items)<3:raise ValueError('Years must be unique and ascending')
    return items


def _mean(rows,key):
    return sum(r[key] for r in rows)/len(rows)


def historical_ratio(rows):
    """League rate ratio: POST runs per *team* game / REG per team game."""
    if not rows:raise ValueError('No completed historical seasons')
    return _mean(rows,'Post_Runs_Per_Game')/_mean(rows,'Reg_Runs_Per_Game')


def context_for_game(day,game_type='R',csv_path=DEFAULT_DATA,
                     include_2026_snapshot=True):
    d=day if isinstance(day,date) else date.fromisoformat(str(day)[:10])
    if game_type in ('R','FORECAST','regular','regular_season'):
        return {'active':False,'factor':1.0,'raw_ratio':1.,'run_multiplier':1.,
                'reason':'Regular season: no postseason overlay','season':d.year}
    rows=load_years(csv_path)
    # 2022-2025 were completed seasons and can be used only in subsequent years.
    # 2026 is an October 11 partial snapshot, NOT a completed 2026 season.
    # Never reuse that partial cohort as a future year's full-season prior.
    prior=[r for r in rows if r['Year']<d.year and r['Year']<=2025]
    if not prior:
        return {'active':False,'factor':1.,'raw_ratio':1.,'run_multiplier':1.,
                'reason':'No documented prior complete seasons','season':d.year}
    prior=prior[-4:]
    base=historical_ratio(prior)
    current=None
    if d.year==2026 and d>=FIRST_2026_SNAPSHOT_DATE and include_2026_snapshot:
        current=next((r for r in rows if r['Year']==2026),None)
    if current:
        curr_ratio=current['Post_Runs_Per_Game']/current['Reg_Runs_Per_Game']
        blended=(1-CURRENT_SEASON_BLEND)*base+CURRENT_SEASON_BLEND*curr_ratio
        source='2022-2025 completed-season prior + 2026 data published by Oct 11'
        rel_share=current['Post_Reliever_IP_Pct']/100.
        hr_ratio=current['Post_HR_Per_Game']/current['Reg_HR_Per_Game']
        velo_delta=current['Post_Avg_Fastball_MPH']-current['Reg_Avg_Fastball_MPH']
    else:
        blended=base
        source='previous completed seasons only'
        rel_share=_mean(prior,'Post_Reliever_IP_Pct')/100.
        hr_ratio=_mean(prior,'Post_HR_Per_Game')/_mean(prior,'Reg_HR_Per_Game')
        velo_delta=_mean(prior,'Post_Avg_Fastball_MPH')-_mean(prior,'Reg_Avg_Fastball_MPH')
    # Blend against existing trained regular-season mean rather than applying
    # the full historical suppression blindly. Not claimed calibrated.
    factor=1+CONTEXT_STRENGTH*(blended-1)
    return {
      'active':True,'season':d.year,'factor':float(factor),
      'run_multiplier':float(factor),'raw_ratio':float(blended),
      'completed_years_used':[r['Year'] for r in prior],
      'current_2026_snapshot_used':bool(current),
      'earliest_2026_snapshot_eligible':FIRST_2026_SNAPSHOT_DATE.isoformat(),
      'prior_ratio':float(base),'blend_2026_weight':CURRENT_SEASON_BLEND if current else 0.,
      'context_strength':CONTEXT_STRENGTH,
      'post_reliever_share':float(rel_share),
      'post_home_run_rate_ratio':float(hr_ratio),
      'post_fastball_velocity_increase_mph':float(velo_delta),
      'source':source,
      'status':'Experimental postseason scoring scenario: NOT verified to beat holdouts',
      'warning':'Non-scoring columns come from user-supplied estimates and are audit-only. '
                'Relief/HR/velocity are correlated with run environment; do not multiply their effects. '
                'The 2026 aggregate is barred from replays dated before Oct 12.'}


def with_context_rates(home_mu,away_mu,context):
    f=float(context['factor'])
    if not 0.6<=f<=1.1:raise ValueError('Unexpected postseason multiplier')
    return float(home_mu)*f,float(away_mu)*f


def retrospective_season_diagnostics(path=DEFAULT_DATA):
    rows=load_years(path)
    results=[]
    for current in rows:
        yr=current['Year']
        prior=[r for r in rows if r['Year']<yr and r['Year']<=2025]
        if not prior:continue
        p=historical_ratio(prior[-4:])
        obs=current['Post_Runs_Per_Game']/current['Reg_Runs_Per_Game']
        contextual=1+CONTEXT_STRENGTH*(p-1)
        results.append({'year':yr,'historic_prior_ratio':round(p,4),
           'observed_ratio':round(obs,4),'shrunken_forecast_ratio':round(contextual,4),
           'absolute_baseline_error':round(abs(1-obs),4),
           'absolute_scenario_error':round(abs(contextual-obs),4),
           'note':'Annual league averages only; NOT a game-level backtest'})
    return results
