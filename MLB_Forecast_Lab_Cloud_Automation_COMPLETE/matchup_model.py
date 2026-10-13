"""Pregame-only, research-grade MLB matchup prototype.

The Elo baseline remains the default recommendation. This expanded winner model
adds prior offense, team bullpen-use proxies, starting-pitcher start histories,
known starter handedness, and manager pitching tendencies. Additional *actual*
starter/bullpen statistics are used ONLY when an optional Retrosheet detail
import is available. Never label team runs allowed as a pitcher's ERA.

Inputs always precede the requested game DATE (all games on a date updated
as a batch). 2023-24 training, 2025 and 2026 untouched evaluations.
"""
from __future__ import annotations
from collections import defaultdict, deque
from datetime import date, datetime
from itertools import groupby
from pathlib import Path
import csv
import json
import math
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from backtest import metrics
from extended_eval import K, HOME_ELO, OFFSEASON


def as_date(d):
    return pd.Timestamp(d).date()


def safe_float(v,default=0.0):
    try:
        n=float(v)
        return n if math.isfinite(n) else default
    except (TypeError,ValueError): return default


def avg(xs,default):return sum(xs)/len(xs) if xs else default


def loaded_details(data_dir:Path):
    """Load OPTIONAL retrospective measurements keyed by date/team/opponent.

    Retrosheet supplemental data / MLB box scores contain ACTUAL starter outs,
    strikeouts etc. The standard game logs do not. No automatic imputation.
    """
    details={};hands={};directory={}
    path=Path(data_dir)/'advanced_pitching_details.csv'
    if path.exists():
        with path.open(newline='',encoding='utf-8-sig') as fh:
            for row in csv.DictReader(fh):
                d=row.get('date','')[:10]; side=row.get('side','')
                if d and side in ('home','away'):
                    base=(d,row.get('home'),row.get('away'),side)
                    number=str(row.get('game_num') or '').strip()
                    gid=str(row.get('game_id') or '').strip()
                    # Retrosheet GL202x files supply game_num; MLB exports game_id.
                    # Store both lookup paths when available, but reject true collisions.
                    keys=[]
                    if number:keys.append(base+('num:'+number,))
                    if gid:keys.append(base+('gid:'+gid,))
                    if not keys:keys.append(base)  # backward-compatible single-game rows
                    for key in keys:
                        if key in details and details[key]!=row:
                            raise ValueError(f'Duplicate pitching details: {key}')
                        details[key]=row
    path=Path(data_dir)/'pitcher_directory.csv'
    if path.exists():
        with path.open(newline='',encoding='utf-8-sig') as fh:
            for row in csv.DictReader(fh):
                pid=str(row.get('pitcher_id','')).strip();name=row.get('name','').strip()
                hand=str(row.get('hand','')).strip().upper()
                if pid and hand in ('L','R'):hands[pid]=hand
                if name and pid:
                    directory.setdefault(name.casefold(),set()).add(pid)
    return details,hands,directory


def enrich_games(games,details,hands):
    """Attach observed post-game pitching data, NEVER pregame for that date."""
    enriched=[];count=0
    # A legacy row with no game number must not attach to BOTH doubleheader games.
    from collections import Counter
    base_counts=Counter((as_date(g['date']).isoformat(),g['home'],g['away']) for g in games)
    for game in games:
        g=game.copy();day=as_date(g['date']).isoformat()
        for side in ('home','away'):
            base=(day,g['home'],g['away'],side)
            num=str(g.get('game_num') or '').strip()
            gid=str(g.get('game_id') or '').strip()
            # MLB schedule rows are mapped by extended_eval.all_games to
            # game_num='824621' and game_id='api-824621'. Their MLB boxscore
            # details use the *raw* game_id='824621' with no game_num.
            # Try both exact IDs and the explicitly typed API namespace;
            # never fall back to a non-unique date/team key for doubleheaders.
            rec=(details.get(base+('num:'+num,)) if num else None)
            raw_api_id=gid[4:] if gid.startswith('api-') and gid[4:].isdigit() else ''
            if rec is None and gid:
                rec=details.get(base+('gid:'+gid,))
            if rec is None and raw_api_id:
                rec=details.get(base+('gid:'+raw_api_id,))
            if rec is None and base_counts[base[:3]]==1:
                rec=details.get(base) # legacy unnumbered row: safe only for a single game
            if not rec:continue
            count+=1
            pid=rec.get('pitcher_id') or g.get(side+'_sp','')
            g[side+'_sp']=pid
            for col in ('sp_outs','sp_er','sp_k','sp_bb','sp_hr','bp_outs','bp_er','bp_pitches','sp_pitches','pitchers_used'):
                if rec.get(col) not in ('',None):g[side+'_'+col]=safe_float(rec[col],float('nan'))
            hand=rec.get('sp_hand','').upper()
            if hand in ('L','R'):
                g[side+'_sp_hand']=hand
                if pid:hands[pid]=hand
            mgr=str(rec.get('manager_id') or '')
            if mgr:g[side+'_manager']=mgr
        enriched.append(g)
    return enriched,count


class Team:
    def __init__(self):
        self.history=deque(maxlen=75)
        self.last=None

    def signals(self,day,opponent_hand):
        recent=list(self.history)
        last15=recent[-15:];last40=recent[-40:]
        split=[x for x in recent if x['opp_hand']==opponent_hand] if opponent_hand in ('L','R') else []
        def obp(sample):
            hits=sum(x['hits'] for x in sample); walks=sum(x['walks'] for x in sample)
            hbp=sum(x['hbp'] for x in sample); ab=sum(x['ab'] for x in sample)
            sf=sum(x['sf'] for x in sample)
            # The fallback is MLB-scale league mean, not the current game's outcome.
            return (hits+walks+hbp+80*.315)/(ab+walks+hbp+sf+80) if sample else .315
        def iso(sample):
            xb=sum(x['doubles']+2*x['triples']+3*x['hr'] for x in sample)
            ab=sum(x['ab'] for x in sample)
            return (xb+80*.155)/(ab+80) if sample else .155
        last3=[x for x in recent if (day-x['day']).days<=3]
        last7=[x for x in recent if (day-x['day']).days<=7]
        bp_recent=[x for x in last3 if x['bp_outs'] is not None]
        rest=4.0 if self.last is None else min(8,max(0,(day-self.last).days-1))
        return dict(rpg15=avg([x['scored'] for x in last15],4.5),
            ra15=avg([x['allowed'] for x in last15],4.5),
            rpg40=avg([x['scored'] for x in last40],4.5),
            obp15=obp(last15),iso15=iso(last15),
            split_rpg=avg([x['scored'] for x in split[-30:]],4.5),
            split_n=len(split[-30:]),rest=rest,
            # Relief pitchers used is a proxy for bullpen usage, NOT actual workload.
            bp_used3=sum(x['relievers'] for x in last3),
            bp_used7=sum(x['relievers'] for x in last7),
            bp_outs3=sum(x['bp_outs'] for x in bp_recent),
            bp_known3=len(bp_recent),
            bp_er9=(sum(x['bp_er'] for x in last15 if x['bp_er'] is not None)*27 /
                   max(1,sum(x['bp_outs'] for x in last15 if x['bp_outs'] is not None)))
                   if any(x['bp_outs'] for x in last15) else 4.3)

    def record(self,day,scored,allowed,game,side,opponent_hand):
        def field(k):return safe_float(game.get(side+'_'+k))
        def optional(k):
            v=game.get(side+'_'+k)
            return safe_float(v) if v is not None and not pd.isna(v) else None
        self.history.append(dict(day=day,scored=scored,allowed=allowed,
            hits=field('hits'),walks=field('walks'),hbp=field('hbp'),ab=field('ab'),
            sf=field('sf'),doubles=field('2b'),triples=field('3b'),hr=field('hr'),
            relievers=max(0,field('pitchers_used')-1),opp_hand=opponent_hand,
            bp_outs=optional('bp_outs'),bp_er=optional('bp_er')))
        self.last=day


class Starter:
    def __init__(self): self.st=[];self.last=None
    def signals(self,day):
        rec=self.st[-8:];actual=[r for r in rec if r['outs'] is not None and r['er'] is not None]
        outs=sum(r['outs'] for r in actual);er=sum(r['er'] for r in actual)
        kk=sum(r['k'] for r in actual);bb=sum(r['bb'] for r in actual)
        return dict(starts=len(rec), team_allowed=avg([r['allowed'] for r in rec],4.5),
            rest=6 if self.last is None else min(15,max(0,(day-self.last).days-1)),
            earned_era=(er*27+18*4.3)/(outs+18) if actual else 4.3,
            kbb=(kk+8)/(bb+4) if actual else 2.0,
            innings=avg([r['outs']/3 for r in actual[-4:]],5.0),
            known=len(actual))
    def record(self,day,game,side,allowed):
        def opt(k):
            v=game.get(side+'_'+k)
            return safe_float(v) if v is not None and not pd.isna(v) else None
        self.st.append(dict(allowed=allowed,outs=opt('sp_outs'),er=opt('sp_er'),
            k=opt('sp_k') or 0,bb=opt('sp_bb') or 0))
        self.last=day


class Manager:
    def __init__(self): self.r=deque(maxlen=60)
    def signals(self):
        r=list(self.r)
        return dict(bp_use=avg([z['relievers'] for z in r[-20:]],3.0),
          hook_innings=avg([z['starter_ip'] for z in r[-20:] if z['starter_ip'] is not None],5.0),
          games=len(r))
    def record(self,game,side):
        outs=game.get(side+'_sp_outs')
        ip=safe_float(outs)/3 if outs is not None and not pd.isna(outs) else None
        used=max(0,safe_float(game.get(side+'_pitchers_used'))-1)
        self.r.append(dict(relievers=used,starter_ip=ip))


# Model parameters are fixed based on training/validation only; columns are
# static, allowing missing 2026 box-score detail to result in honest neutral
# feature values instead of silently making up pitcher data.
COVARIATES=['elo_logit',
 'offense_rpg15_diff','offense_rpg40_diff','run_allowed_diff',
 'offense_obp_diff','offense_iso_diff','platoon_run_diff','platoon_known_diff',
 'rest_diff','bullpen_used3_diff','bullpen_used7_diff',
 'bullpen_outs3_diff','bullpen_known_diff','bullpen_er9_diff',
 'sp_start_quality_diff','sp_starts_diff','sp_rest_diff',
 'sp_era_diff','sp_kbb_diff','sp_innings_diff','sp_known_diff',
 'manager_bp_use_diff','manager_hook_diff','manager_known_diff',
 'postseason_flag']


def _row(day,game,teams,starters,managers,hand_map,rating,year):
    h=game['home'];a=game['away'];hs=str(game.get('home_sp') or '');as_=str(game.get('away_sp') or '')
    hhand=str(game.get('home_sp_hand') or hand_map.get(hs,'')).upper()
    ahand=str(game.get('away_sp_hand') or hand_map.get(as_,'')).upper()
    th=teams[h].signals(day,ahand);ta=teams[a].signals(day,hhand)
    sp_h=starters[hs].signals(day) if hs else Starter().signals(day)
    sp_a=starters[as_].signals(day) if as_ else Starter().signals(day)
    mh=managers[str(game.get('home_manager') or '')].signals()
    ma=managers[str(game.get('away_manager') or '')].signals()
    ph=rating.get(h,0);pa=rating.get(a,0)
    elo=1/(1+10**((pa-ph-HOME_ELO)/400))
    row={'date':pd.Timestamp(day),'year':year,'game_id':game.get('game_id',''),
         'home':h,'away':a,'game_type':game.get('game_type','R'),
         'home_sp':hs,'away_sp':as_,'home_sp_hand':hhand,'away_sp_hand':ahand,
         'home_sp_known':sp_h['known'],'away_sp_known':sp_a['known'],
         'home_sp_starts':sp_h['starts'],'away_sp_starts':sp_a['starts'],
         'home_sp_era':sp_h['earned_era'],'away_sp_era':sp_a['earned_era'],
         'home_bp_used3':th['bp_used3'],'away_bp_used3':ta['bp_used3'],
         'home_bp_outs3':th['bp_outs3'],'away_bp_outs3':ta['bp_outs3'],
         'home_sp_split_n':th['split_n'],'away_sp_split_n':ta['split_n'],
         'home_elo':elo,'home_elo_rating':ph,'away_elo_rating':pa,
         'y_home':int(game['home_final']>game['away_final'])}
    row.update(dict(elo_logit=math.log(elo/(1-elo)),
       offense_rpg15_diff=th['rpg15']-ta['rpg15'],offense_rpg40_diff=th['rpg40']-ta['rpg40'],
       run_allowed_diff=ta['ra15']-th['ra15'],
       offense_obp_diff=(th['obp15']-ta['obp15'])*10,
       offense_iso_diff=(th['iso15']-ta['iso15'])*10,
       platoon_run_diff=th['split_rpg']-ta['split_rpg'],
       platoon_known_diff=th['split_n']-ta['split_n'],
       rest_diff=th['rest']-ta['rest'],
       bullpen_used3_diff=ta['bp_used3']-th['bp_used3'],
       bullpen_used7_diff=ta['bp_used7']-th['bp_used7'],
       bullpen_outs3_diff=ta['bp_outs3']-th['bp_outs3'],
       bullpen_known_diff=th['bp_known3']-ta['bp_known3'],
       bullpen_er9_diff=ta['bp_er9']-th['bp_er9'],
       sp_start_quality_diff=sp_a['team_allowed']-sp_h['team_allowed'],
       sp_starts_diff=sp_h['starts']-sp_a['starts'],
       sp_rest_diff=sp_h['rest']-sp_a['rest'],
       sp_era_diff=sp_a['earned_era']-sp_h['earned_era'],
       sp_kbb_diff=sp_h['kbb']-sp_a['kbb'],
       sp_innings_diff=sp_h['innings']-sp_a['innings'],
       sp_known_diff=sp_h['known']-sp_a['known'],
       manager_bp_use_diff=ma['bp_use']-mh['bp_use'],
       manager_hook_diff=mh['hook_innings']-ma['hook_innings'],
       manager_known_diff=mh['games']-ma['games'],
       postseason_flag=int(game.get('game_type','R')!='R')))
    return row


def feature_frame(games,hand_map=None):
    """Replay daily batches; scores on game date D affect only future dates."""
    hand_map=hand_map or {}; ordered=sorted(games,key=lambda g:(int(g['year']),as_date(g['date']),str(g.get('game_num',''))))
    teams=defaultdict(Team);starters=defaultdict(Starter);managers=defaultdict(Manager)
    rating={};prev_year=None;out=[]
    for (year,day),grp in groupby(ordered,key=lambda g:(int(g['year']),as_date(g['date']))):
        batch=list(grp)
        if year!=prev_year:
            teams=defaultdict(Team);starters=defaultdict(Starter);managers=defaultdict(Manager)
            if prev_year is not None:rating={k:v*OFFSEASON for k,v in rating.items()}
            prev_year=year
        changes=defaultdict(float)
        for g in batch:
            out.append(_row(day,g,teams,starters,managers,hand_map,rating,year))
            ph=rating.get(g['home'],0.0);pa=rating.get(g['away'],0.0)
            p=1/(1+10**((pa-ph-HOME_ELO)/400))
            delta=K*(int(g['home_final']>g['away_final'])-p)
            changes[g['home']]+=delta;changes[g['away']]-=delta
        for g in batch:
            h=g['home'];a=g['away'];hs=str(g.get('home_sp') or '');as_=str(g.get('away_sp') or '')
            hhand=str(g.get('home_sp_hand') or hand_map.get(hs,'')).upper()
            ahand=str(g.get('away_sp_hand') or hand_map.get(as_,'')).upper()
            teams[h].record(day,safe_float(g['home_final']),safe_float(g['away_final']),g,'home',ahand)
            teams[a].record(day,safe_float(g['away_final']),safe_float(g['home_final']),g,'away',hhand)
            if hs:starters[hs].record(day,g,'home',safe_float(g['away_final']))
            if as_:starters[as_].record(day,g,'away',safe_float(g['home_final']))
            hm=str(g.get('home_manager') or '');am=str(g.get('away_manager') or '')
            if hm:managers[hm].record(g,'home')
            if am:managers[am].record(g,'away')
        for team,d in changes.items():rating[team]=rating.get(team,0.0)+d
    return pd.DataFrame(out)


def choose_model(frame):
    """Tune only in 2024 (train=2023), refit 2023-24; never use 2025/26 for selection."""
    tr=frame[(frame.year==2023)&(frame.game_type=='R')]
    val=frame[(frame.year==2024)&(frame.game_type=='R')]
    full=frame[(frame.year.isin([2023,2024]))&(frame.game_type=='R')]
    if len(tr)<1000 or len(val)<1000:raise ValueError('Need 2023 and 2024 regular seasons')
    best=(float('inf'),None)
    for c in (.003,.03,.3):
        pipe=make_pipeline(StandardScaler(),LogisticRegression(C=c,max_iter=800,random_state=42))
        pipe.fit(tr[COVARIATES].to_numpy(dtype=float),tr.y_home)
        pred=pipe.predict_proba(val[COVARIATES].to_numpy(dtype=float))[:,1]
        brier=float(np.mean((pred-val.y_home.to_numpy())**2))
        if brier<best[0]:best=(brier,c)
    final=make_pipeline(StandardScaler(),LogisticRegression(C=best[1],max_iter=800,random_state=42))
    final.fit(full[COVARIATES].to_numpy(dtype=float),full.y_home)
    return final,{'validation_brier':best[0],'validation_elo_brier':float(np.mean((val.home_elo-val.y_home)**2)),
         'regularization_C':best[1],'train_games':len(full),'validation_games':len(val)}


def paired_day_bootstrap(frame, p_expanded, p_elo, iterations=1500):
    """Confidence interval for Brier improvement (Elo minus expanded).

    Resample GAME DATES, not individual same-day games. This quantifies
    sampling uncertainty, not model specification uncertainty or betting EV.
    """
    if len(frame)<10:return None
    y=frame.y_home.to_numpy(dtype=float)
    e=(np.asarray(p_elo,dtype=float)-y)**2-(np.asarray(p_expanded,dtype=float)-y)**2
    dates=pd.to_datetime(frame.date).dt.strftime('%Y-%m-%d').to_numpy()
    _,inv=np.unique(dates,return_inverse=True)
    sums=np.bincount(inv,weights=e);counts=np.bincount(inv)
    n=len(sums);rng=np.random.default_rng(2026)
    samples=[]
    for _ in range(iterations):
        indices=rng.integers(0,n,size=n)
        samples.append(float(sums[indices].sum()/counts[indices].sum()))
    return [float(np.percentile(samples,2.5)),float(np.percentile(samples,97.5))]


def backtest_expanded(games,data_dir:Path,output_dir:Path|None=None):
    details,hands,directory=loaded_details(data_dir)
    games,count=enrich_games(games,details,hands)
    frame=feature_frame(games,hands)
    model,fitinfo=choose_model(frame)
    target=frame[(frame.year>=2025)&(frame.game_type.isin(['R','P']))].copy()
    target['p_home_expanded']=model.predict_proba(target[COVARIATES].to_numpy(dtype=float))[:,1]
    splits={}
    for yr in (2025,2026):
        for kind in ('R','P'):
            g=target[(target.year==yr)&(target.game_type==kind)]
            label=f'{yr}_'+('postseason' if kind=='P' else 'regular')
            if len(g):
                splits[label]={'n':len(g),'elo':metrics(g.y_home,g.home_elo),
                    'expanded':metrics(g.y_home,g.p_home_expanded),
                    'starter_observed_games':int(((g.home_sp_known>0)&(g.away_sp_known>0)).sum()),
                    'handedness_known_games':int(((g.home_sp_hand.isin(['L','R'])) & (g.away_sp_hand.isin(['L','R']))).sum()),
                    'brier_improvement_elo_minus_expanded':float(g['home_elo'].sub(g.y_home).pow(2).mean()-g['p_home_expanded'].sub(g.y_home).pow(2).mean()),
                    'brier_improvement_ci_95':paired_day_bootstrap(g,g.p_home_expanded,g.home_elo)}
            else:splits[label]={'n':0}
    res={'status':'RESEARCH / non-deployed comparison to existing Elo baseline',
         'details_rows_applied':count,'handed_pitchers':len(hands),'observations':len(frame),
         'fit':fitinfo,'splits':splits,
         'method':'Logistic winner classifier; fixed chronologically lagged team/starter/bullpen/manager features; 2024 C tuning, 2023-24 refit, 2025-26 untouched tests',
         'warnings':['No historical YES quotes; Brier is NOT profitability',
            'Without supplemental pitching data, team runs while a pitcher started is only a proxy, not ERA',
            'Without starter handedness, offense-vs-handedness feature defaults to neutral',
            'Bullpen pitcher count is not equivalent to actual workload',
            '2026 imported schedule rows omit starter identities unless enriched',
            'Do not deploy advanced winner model without independent holdout improvement']}
    if output_dir:
        output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
        (output_dir/'matchup_model_metrics.json').write_text(json.dumps(res,indent=2))
        target[['date','year','game_type','home','away','y_home','home_elo','p_home_expanded',
               'home_sp_known','away_sp_known','home_sp_hand','away_sp_hand']].to_csv(output_dir/'matchup_model_predictions.csv',index=False)
    return res,model,frame,hands,directory


def resolve_starter(text,directory,team=None):
    """Resolve MLB schedule displayed name to Retrosheet directory; no fuzzy guesses."""
    if not text or str(text).casefold() in ('not announced','none'):return ''
    opts=directory.get(str(text).casefold(),set())
    return next(iter(opts)) if len(opts)==1 else ''


def expanded_forecast(games,date_value,home,away,model,hands=None,home_sp='',away_sp='',data_dir=None):
    day=as_date(date_value)
    if day.year<2025:
        raise ValueError('Expanded model trained through 2024; only dates from 2025 onward are valid holdout forecasts.')
    history=[g for g in games if as_date(g['date'])<day]
    # IMPORTANT: trained and forecast features must use the SAME historical
    # optional pitching/handedness observations. Original all_games rows are
    # deliberately immutable; enrich only the strict past-data snapshot here.
    if data_dir is not None:
        detail,observed_hands,_=loaded_details(Path(data_dir))
        observed_hands.update(hands or {})
        history,_=enrich_games(history,detail,observed_hands)
        hands=observed_hands
    fake=dict(date=pd.Timestamp(day),year=day.year,game_num='ZZZZ_FORECAST',game_id='ZZZZ_FORECAST',
       game_type='R',home=home,away=away,home_final=1,away_final=0,
       home_sp=home_sp,away_sp=away_sp)
    frame=feature_frame(history+[fake],hands)
    f=frame[frame.game_id=='ZZZZ_FORECAST']
    if len(f)!=1:raise ValueError('Cannot construct exactly one strictly pregame row')
    row=f.iloc[0]
    p=float(model.predict_proba(f[COVARIATES].to_numpy(dtype=float))[:,1][0])
    return {'p_home_expanded':p,'p_away_expanded':1-p,
       'p_home_elo_internal':float(row.home_elo),
       'home_sp_selected':home_sp or 'Unavailable', 'away_sp_selected':away_sp or 'Unavailable',
       'home_sp_era_observed':int(row.home_sp_known),
       'away_sp_era_observed':int(row.away_sp_known),
       'home_sp_era':float(row.home_sp_era),'away_sp_era':float(row.away_sp_era),
       'home_bp_used_last3':float(row.home_bp_used3),'away_bp_used_last3':float(row.away_bp_used3),
       'home_bp_outs_last3':float(row.home_bp_outs3),'away_bp_outs_last3':float(row.away_bp_outs3),
       'offense_splits_home_games':int(row.home_sp_split_n),
       'offense_splits_away_games':int(row.away_sp_split_n),
       'features_as_of_exclusive':day.isoformat()}


if __name__=='__main__':
    from extended_eval import all_games
    root=Path(__file__).resolve().parent
    print(json.dumps(backtest_expanded(all_games(root/'data',True),root/'data',root/'outputs')[0],indent=2))
