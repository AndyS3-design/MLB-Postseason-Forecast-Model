"""MLB Prediction Lab V4: strictly pre-date matchup features and frozen scoring fit.

Optional 2016–2025 recency-weighted regular-season fit for prospective 2026 forecasts.
Additional lineup/weather overlays are NOT backtest-calibrated by this model.
"""
from __future__ import annotations
from collections import defaultdict,deque
from datetime import date
from itertools import groupby
from pathlib import Path
from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import PoissonRegressor
from matchup_model import Team, Starter, Manager, as_date, safe_float, loaded_details, enrich_games
from forecast_engine import historical_snapshot, elo_probability

VERSION='7.0.0-pregame-recency-weighted'
FEATURES=['is_home','own_rpg15','own_rpg40','own_obp15','own_iso15','own_platoon_rpg','own_platoon_n',
    'opp_ra15','opp_bp_era','opp_bp_outs3','opp_bp_known3','opp_bp_used3',
    'opp_sp_era','opp_sp_kbb','opp_sp_innings','opp_sp_known','opp_sp_rest','own_rest',
    'opp_manager_hook','opp_manager_bp_use','elo_advantage','opp_field_errors15','opp_errors_known15','month']


def _feature(day,own,opp,own_starter,opp_starter,own_manager,opp_manager,starter_hands,elo_adv,is_home):
    opponent_hand=starter_hands.get(opp_starter,'')
    ts=own.signals(day,opponent_hand);os=opp.signals(day,starter_hands.get(own_starter,''))
    sp=opp_starter and opp_starter!='Unknown'
    ss=opp_manager  # Manager object, always available; only historical observations used
    pit=Starter().signals(day) if not sp else None
    return ts,os,pit,ss


def _features(day,side,game,teams,starters,managers,defenses,hands,elo):
    own_team=game[side];opp_side='away' if side=='home' else 'home';opp_team=game[opp_side]
    own_sp=str(game.get(side+'_sp') or '');op_sp=str(game.get(opp_side+'_sp') or '')
    opp_hand=str(game.get(opp_side+'_sp_hand') or hands.get(op_sp) or '').upper()
    own=teams[own_team].signals(day,opp_hand)
    opp=teams[opp_team].signals(day,str(game.get(side+'_sp_hand') or hands.get(own_sp) or '').upper())
    s=starters[op_sp].signals(day) if op_sp else Starter().signals(day)
    manager_id=str(game.get(opp_side+'_manager') or '')
    mg=managers[manager_id].signals() if manager_id else Manager().signals()
    e=float(elo if side=='home' else 1-elo)
    opp_err=list(defenses[opp_team])[-15:]
    vals=[int(side=='home'),own['rpg15'],own['rpg40'],own['obp15'],own['iso15'],own['split_rpg'],
          own['split_n'],opp['ra15'],opp['bp_er9'],opp['bp_outs3'],opp['bp_known3'],opp['bp_used3'],
          s['earned_era'],s['kbb'],s['innings'],s['known'],s['rest'],own['rest'],
          mg['hook_innings'],mg['bp_use'],math.log(max(0.01,min(.99,e))/(1-max(0.01,min(.99,e)))),
          float(np.mean(opp_err)) if opp_err else 0.65,len(opp_err),
          day.month]
    return dict(zip(FEATURES, (float(v) for v in vals)))


def historical_team_rows(games:list[dict],hands:dict|None=None):
    """Create two rows per game, collecting all features BEFORE any outcomes that date.

    Row labels are for evaluation/training only; never enter FEATURES.
    """
    hands=hands or {}
    gms=sorted(games,key=lambda g:(int(g['year']),as_date(g['date']),str(g.get('game_num',''))))
    from extended_eval import K,HOME_ELO,OFFSEASON
    ratings={};season=None;teams=defaultdict(Team);starters=defaultdict(Starter);managers=defaultdict(Manager);defenses=defaultdict(lambda:deque(maxlen=35))
    out=[]
    for (year,day),grp in groupby(gms,key=lambda g:(int(g['year']),as_date(g['date']))):
        group=list(grp)
        if year!=season:
            teams=defaultdict(Team);starters=defaultdict(Starter);managers=defaultdict(Manager);defenses=defaultdict(lambda:deque(maxlen=35))
            if season is not None:ratings={k:v*OFFSEASON for k,v in ratings.items()}
            season=year
        elo_delta=defaultdict(float)
        for game in group:
            h=game['home'];a=game['away']
            eh=ratings.get(h,0);ea=ratings.get(a,0)
            p=1/(1+10**((ea-eh-HOME_ELO)/400))
            for side in ('home','away'):
                x=_features(day,side,game,teams,starters,managers,defenses,hands,p)
                x.update(date=day.isoformat(),year=year,game_id=str(game.get('game_id') or ''),
                         game_num=str(game.get('game_num') or ''),side=side,
                         team=game[side],opponent=game['away' if side=='home' else 'home'],
                         game_type=game.get('game_type','R'),
                         runs_actual=(int(game[side+'_reg']) if pd.notna(game.get(side+'_reg')) else int(game[side+'_final'])),
                         winner_actual=int(game[side+'_final']>game[('away' if side=='home' else 'home')+'_final']))
                out.append(x)
            elo_delta[h]+=K*(int(game['home_final']>game['away_final'])-p)
            elo_delta[a]-=K*(int(game['home_final']>game['away_final'])-p)
        for game in group:
            h=game['home'];a=game['away']
            hs=str(game.get('home_sp') or '');aps=str(game.get('away_sp') or '')
            hh=str(game.get('home_sp_hand') or hands.get(hs,'')).upper();ah=str(game.get('away_sp_hand') or hands.get(aps,'')).upper()
            teams[h].record(day,safe_float(game['home_final']),safe_float(game['away_final']),game,'home',ah)
            teams[a].record(day,safe_float(game['away_final']),safe_float(game['home_final']),game,'away',hh)
            if hs:starters[hs].record(day,game,'home',safe_float(game['away_final']))
            if aps:starters[aps].record(day,game,'away',safe_float(game['home_final']))
            for side in ('home','away'):
                err=game.get(side+'_errors')
                if err is not None and pd.notna(err):defenses[game[side]].append(float(err))
                manager=str(game.get(side+'_manager') or '')
                if manager:managers[manager].record(game,side)
        for t,delta in elo_delta.items():ratings[t]=ratings.get(t,0)+delta
    return pd.DataFrame(out)


def pregame_rows(history,day,home,away,home_sp='',away_sp='',hands=None,home_manager='',away_manager=''):
    d=as_date(day)
    past=historical_snapshot(history,d)
    # Only the sentinel outcome is synthetic. It is never used as a feature, and is removed before data update.
    sentinel=dict(date=pd.Timestamp(d),year=d.year,game_num='ZZZ_V4_ONLY',game_id='ZZZ_V4_ONLY',
            home=home,away=away,home_sp=home_sp,away_sp=away_sp,
            home_manager=home_manager,away_manager=away_manager,
            game_type='FORECAST',home_final=1,away_final=0)
    rows=historical_team_rows(past+[sentinel],hands)
    selected=rows[rows.game_id=='ZZZ_V4_ONLY']
    if len(selected)!=2:raise ValueError('Expected two and only two forecast team rows')
    return selected


@dataclass
class FrozenRunFit:
    pipeline:object
    alpha:float
    validation_poisson_deviance:float
    training_rows:int
    validation_rows:int
    features:list[str]
    training_years:list[int] | None = None
    coverage_note:str = ""


def _poisson_loss(actual,pred):
    y=np.asarray(actual,dtype=float);p=np.clip(np.asarray(pred,dtype=float),.2,20)
    return float(np.mean(p-y*np.log(p))) # differs from full NLL by constant only


def _recency_weights(frame,reference_year,half_life_years=3.0):
    # Historical seasons count less than recent ones. Both scaler and regressor
    # receive these weights so the 2016 scoring environment cannot dominate.
    age=np.maximum(0,reference_year-frame.year.to_numpy(dtype=float))
    return np.power(0.5,age/half_life_years)


def _weighted_poisson_fit(frame,columns,alpha,reference_year):
    fit=make_pipeline(StandardScaler(),PoissonRegressor(alpha=alpha,max_iter=300))
    w=_recency_weights(frame,reference_year)
    X=frame[columns].to_numpy(dtype=float)
    fit.fit(X,frame.runs_actual.to_numpy(dtype=float),
            standardscaler__sample_weight=w,poissonregressor__sample_weight=w)
    return fit


def train_frozen_run_model(rows):
    """Tune on 2024, then train regular-season data through 2025 for 2026.

    2016–2022 files are optional; if incomplete, report the coverage explicitly.
    2026 games are NEVER training labels. 2024 was used for model selection;
    2025 has previously informed development and is not an untouched test.
    """
    df=rows[(rows.game_type=='R')&(rows.year>=2016)&(rows.year<=2025)].copy()
    tr=df[df.year<=2023];val=df[df.year==2024]
    if len(tr)<3500 or len(val)<3500:
        raise ValueError('Need 2023 and 2024 regular-season training and validation games.')
    candidates=[(.1,True),(1.,True),(10.,True),(.1,False),(1.,False),(10.,False)]
    scored=[]
    for alpha,use_defense in candidates:
        cols=FEATURES if use_defense else [f for f in FEATURES
             if not f.startswith('opp_field_errors') and not f.startswith('opp_errors_known')]
        model=_weighted_poisson_fit(tr,cols,alpha,reference_year=2023)
        p=model.predict(val[cols].to_numpy(dtype=float))
        scored.append((_poisson_loss(val.runs_actual,p),alpha,use_defense))
    best_loss,chosen,defense=min(scored)
    cols=FEATURES if defense else [f for f in FEATURES
         if not f.startswith('opp_field_errors') and not f.startswith('opp_errors_known')]
    final=_weighted_poisson_fit(df,cols,chosen,reference_year=2025)
    years=sorted(int(x) for x in df.year.unique())
    missing=sorted(set(range(2016,2026))-set(years))
    coverage=('10 seasons: 2016–2025' if not missing else
              f'{len(years)} seasons loaded; missing years {missing}')
    return FrozenRunFit(final,chosen,best_loss,len(df),len(val),cols,
                        training_years=years,coverage_note=coverage)


def predict_rates(fit:FrozenRunFit,rows):
    vals=fit.pipeline.predict(rows[fit.features].to_numpy(dtype=float))
    return [float(np.clip(v,1.,11.)) for v in vals]


def paired_run_validation(fit,rows,year=2025):
    selected=rows[(rows.year==year)&(rows.game_type=='R')]
    if len(selected)==0:return {'status':'unavailable','n':0}
    y=selected.runs_actual.to_numpy(dtype=float)
    p=np.asarray(predict_rates(fit,selected),dtype=float)
    base=np.full_like(y,4.5)
    vals=dict(n=len(y)//2,
      avg_run_mae=float(np.mean(np.abs(y-p))), baseline_mae=float(np.mean(np.abs(y-base))),
      mean_poisson_score=float(_poisson_loss(y,p)),baseline_poisson_score=float(_poisson_loss(y,base)))
    vals['improvement_mae']=vals['baseline_mae']-vals['avg_run_mae']
    return vals


def make_forecast(games,data_dir,day,home,away,home_sp='',away_sp='',history_cache=None,fit_cache=None):
    day=as_date(day)
    history=historical_snapshot(games,day)
    if not history:raise ValueError('Historical MLB results are required before forecast day')
    if history_cache is None:
        details,hands,_=loaded_details(Path(data_dir))
        enriched,n=enrich_games(games,details,hands)
    else:
        enriched,hands,n=history_cache
    fit=fit_cache or train_frozen_run_model(historical_team_rows(enriched,hands))
    e_home,_,_=elo_probability(history,day,home,away)
    recent=pregame_rows(enriched,day,home,away,home_sp,away_sp,hands)
    values=predict_rates(fit,recent)
    hrow=recent[recent.side=='home'].iloc[0];arow=recent[recent.side=='away'].iloc[0]
    return dict(home=home,away=away,date=day.isoformat(),elo_home=float(e_home),
        home_mu=values[0] if recent.iloc[0].side=='home' else values[1],
        away_mu=values[0] if recent.iloc[0].side=='away' else values[1],
        home_features=hrow.to_dict(),away_features=arow.to_dict(),
        training=dict(model_version=VERSION,alpha=fit.alpha,training_rows=fit.training_rows,
            validation_score_2024=fit.validation_poisson_deviance,
            detailed_records_matched=n,cutoff_exclusive=day.isoformat()),
        warnings=['Winner and scoring are derived from the SAME simulated run distribution, not forced to Elo.',
            '2025/2026 have informed prior model development: backtest is retrospective, not a fresh prospective holdout.',
            'Lineup and weather adjustments are scenario-based unless separately calibrated.'])
