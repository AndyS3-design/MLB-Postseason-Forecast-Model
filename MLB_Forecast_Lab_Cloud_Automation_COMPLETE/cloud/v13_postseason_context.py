"""Time-gated official postseason scoring calibration from 2020–2025 finals.

Coefficient selection (2022–25 chronological study): strength 1.20 and
80 completed-game prior-equivalent smoothing. Its 2022–25 game-level MAE
was within 0.005 combined runs of the best historical candidate, while
retaining controlled adaptation to earlier completed games in 2026.

2026 finals used in live forecasts MUST be strictly BEFORE the game date.
The earlier saved original/preliminary forecasts must never be modified.
"""
from __future__ import annotations
import csv,math
from datetime import date
from pathlib import Path

GAME_TYPES={'F','D','L','W'}
STRENGTH=1.2
PRIOR_EQUIVALENT_GAMES=80
START_YEAR=2020
HISTORIC_END=2025

# Independently computed from Retrosheet complete regular-season game logs.
# 2026 is read from the official MLB regular-season local CSV, not hardcoded.
REG_RUNS_COMBINED={
 2020:9.291759465478842,2021:9.06134211609716,
 2022:8.566666666666666,2023:9.231275720164609,
 2024:8.786743515850145,2025:8.894650205761317
}


def _date(value):
    return date.fromisoformat(str(value)[:10])


def _load(path,year=None,cutoff=None):
    if not Path(path).is_file():return []
    unique={}
    with Path(path).open(newline='',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            try:
                yr=int(row['year'])
                day=_date(row['date'])
                if year is not None and yr!=year:continue
                if cutoff is not None and not day<cutoff:continue
                if row.get('game_type') not in GAME_TYPES:continue
                ident=str(row['game_id'])
                if not ident:continue
                if 'total_runs' in row:
                    total=int(row['total_runs'])
                else:
                    total=int(row['away_final'])+int(row['home_final'])
                if total<0:continue
            except (ValueError,TypeError,KeyError):
                continue
            if ident in unique:
                if unique[ident]!=(yr,day,total):
                    raise ValueError('Conflicting final game ID '+ident)
            unique[ident]=(yr,day,total)
    return [{'year':y,'date':d,'total_runs':t,'game_id':k}
            for k,(y,d,t) in unique.items()]


def _regular_rate(root,year):
    if year<=HISTORIC_END:return REG_RUNS_COMBINED[year]
    path=Path(root)/'data'/f'mlb_{year}_regular.csv'
    scores=[]
    if path.is_file():
        with path.open(newline='',encoding='utf-8-sig') as stream:
            for r in csv.DictReader(stream):
                try:
                    scores.append(int(r['away_final'])+int(r['home_final']))
                except (TypeError,ValueError,KeyError):
                    continue
    return sum(scores)/len(scores) if len(scores)>500 else None


def context_for_game(day,game_type,root,include_2026_snapshot=True):
    day=_date(day);season=day.year
    inactive={'active':False,'season':season,'factor':1.0,'run_multiplier':1.0,
              'raw_ratio':1.0,'reason':'Regular-season game or insufficient complete historical data'}
    if str(game_type) not in GAME_TYPES:return inactive
    root=Path(root)
    path=root/'data'/'official_postseason_2020_2025.csv'
    all_historical=_load(path)
    # A source gap must not silently make a confident new multiplier.
    available={int(r['year']) for r in all_historical}
    previous=[yr for yr in range(max(START_YEAR,season-4),min(season,HISTORIC_END+1))
              if yr in available and yr in REG_RUNS_COMBINED]
    if len(previous)<2:return {**inactive,'reason':'Fewer than two official complete prior postseason seasons'}
    records=[r for r in all_historical if r['year'] in previous]
    if len(records)<65:return {**inactive,'reason':'Fewer than 65 historical postseason final games'}
    history_mean=sum(r['total_runs'] for r in records)/len(records)
    weighted_regular=sum(sum(1 for r in records if r['year']==year)*REG_RUNS_COMBINED[year]
                         for year in previous)/len(records)
    historical_ratio=history_mean/weighted_regular
    reg_rate=_regular_rate(root,season)
    if reg_rate is None or not math.isfinite(reg_rate):
        return {**inactive,'reason':'Current regular-season scoring baseline unavailable'}
    partial=[]
    if season==2026 and include_2026_snapshot:
        # No current-year postseason results on or after the game date.
        partial=_load(root/'data/mlb_postseason_2023_2026.csv',year=season,cutoff=day)
    elif season>2026:
        partial=_load(root/'data/mlb_postseason_2023_2026.csv',year=season,cutoff=day)
    n=len(partial)
    observed=sum(r['total_runs'] for r in partial)/n/reg_rate if n else None
    shrink=n/(n+PRIOR_EQUIVALENT_GAMES)
    blended=(1-shrink)*historical_ratio+shrink*observed if n else historical_ratio
    factor=1+STRENGTH*(blended-1)
    if not 0.6<=factor<=1.1:
        raise ValueError('Historical postseason multiplier outside plausible bounds')
    return {'active':True,'season':season,'factor':float(factor),
        'run_multiplier':float(factor),'raw_ratio':float(blended),
        'historical_ratio':float(historical_ratio),
        'completed_years_used':previous,'historic_games_used':len(records),
        'current_prior_games_used':n,'current_prior_runs_per_team_game':
            (sum(r['total_runs'] for r in partial)/(2*n) if n else None),
        'current_regular_runs_per_team_game':reg_rate/2,
        'adaptive_weight':float(shrink),'context_strength':STRENGTH,
        'prior_equivalent_games':PRIOR_EQUIVALENT_GAMES,
        'current_2026_snapshot_used':n>0,
        'features_cutoff_exclusive':day.isoformat(),
        'source':'Official MLB archived 2020–25 postseason finals, verified regular-season totals; prior-date-only 2026 MLB finals',
        'status':'Historically checked conservative scoring adjustment; not yet proved on untouched game-specific forecasts',
        'warning':'Game-specific context and inferred pitching effects remain uncertain. Postseason scoring changes do not guarantee a low-scoring game.'}


def with_context_rates(home,away,context):
    factor=float(context['factor'])
    if not 0.6<=factor<=1.1:raise ValueError('Unexpected postseason correction')
    return float(home)*factor,float(away)*factor
