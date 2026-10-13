#!/usr/bin/env python3
"""Reproducible MLB regular-season probability backtest using Retrosheet game logs.

Train: 2023; validate/tune run dispersion: 2024; final fit: 2023-24;
untouched test: 2025. Features are calculated chronologically from PRIOR games.
Nothing is inferred from the current game's runs, hits, or pitcher performance.

Data copyright Retrosheet. See README.md for attribution and limitations.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict, deque
from dataclasses import dataclass
from io import TextIOWrapper
from pathlib import Path
import json
import re
import urllib.request
import zipfile
import numpy as np
import pandas as pd
from scipy.stats import poisson, nbinom
from sklearn.ensemble import HistGradientBoostingRegressor

SEASONS = (2023, 2024, 2025)
FEATURE_NAMES = [
    'home_rpg15', 'away_rpg15', 'home_ra15', 'away_ra15',
    'home_rpg45','away_rpg45','home_ra45','away_ra45',
    'home_season_rpg','away_season_rpg','home_season_ra','away_season_ra',
    'home_rest','away_rest','home_sp_allowed','away_sp_allowed',
    'home_sp_starts','away_sp_starts',
    'home_games','away_games','league_rpg','month'
]
SCORE_RE = re.compile(r'\(\d+\)|\d|[xX]')

def download_logs(data_dir: Path, seasons=SEASONS):
    data_dir.mkdir(parents=True, exist_ok=True)
    for y in seasons:
        dest = data_dir / f'gl{y}.zip'
        txt = data_dir / f'GL{y}.TXT'
        if dest.exists() or txt.exists():
            continue
        url = f'https://www.retrosheet.org/gamelogs/gl{y}.zip'
        print(f'Downloading {url} ...', flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as exc:
            if dest.exists(): dest.unlink()
            raise RuntimeError(
                f'Cannot download {url}. Download gl{y}.zip manually from '
                'https://www.retrosheet.org/gamelogs/ and put it in --data-dir. '
                f'Network error: {exc}'
            ) from exc

def read_rows(data_dir: Path):
    games=[]
    for year in SEASONS:
        zpath=data_dir/f'gl{year}.zip'
        tpath=data_dir/f'GL{year}.TXT'
        if zpath.exists():
            with zipfile.ZipFile(zpath) as archive:
                names=[n for n in archive.namelist() if n.lower().endswith(('.txt','.csv'))]
                target=next((n for n in names if f'{year}' in n), names[0] if names else None)
                if target is None: raise ValueError(f'No game-log text in {zpath}')
                with archive.open(target) as raw:
                    rows=list(csv.reader(TextIOWrapper(raw, encoding='latin-1')))
        elif tpath.exists():
            with open(tpath,encoding='latin-1',newline='') as f: rows=list(csv.reader(f))
        else:
            raise FileNotFoundError(f'Missing gl{year}.zip or GL{year}.TXT in {data_dir}')
        for r in rows:
            if len(r)<105: continue
            try:
                d=pd.Timestamp(r[0]);away=int(r[9]);home=int(r[10]);outs=int(r[11]);
            except (ValueError,TypeError,IndexError): continue
            if d.year!=year or away<0 or home<0 or outs<45 or r[14].strip(): continue
            # postseason games do NOT occur in the regular-season GLyear archives.
            reg_away=parse_regulation(r[19]);reg_home=parse_regulation(r[20]);
            if reg_away is None or reg_home is None or reg_away>away or reg_home>home: continue
            if away==home: continue
            games.append(dict(date=d,year=year,game_num=str(r[1]),away=r[3],home=r[6],
                              away_final=away,home_final=home,away_reg=reg_away,home_reg=reg_home,
                              away_sp=r[101].strip(),home_sp=r[103].strip(),
                              # Retrosheet game-log team batting and pitcher-use totals.
                              # These are results, never used until the NEXT game date.
                              away_pitchers_used=int(r[38] or 0),home_pitchers_used=int(r[66] or 0),
                              away_ab=int(r[21] or 0),away_hits=int(r[22] or 0),
                              away_walks=int(r[30] or 0),away_hbp=int(r[29] or 0),
                              away_sf=int(r[28] or 0),away_2b=int(r[23] or 0),
                              away_3b=int(r[24] or 0),away_hr=int(r[25] or 0),
                              home_ab=int(r[49] or 0),home_hits=int(r[50] or 0),
                              home_walks=int(r[58] or 0),home_hbp=int(r[57] or 0),
                              home_sf=int(r[56] or 0),home_2b=int(r[51] or 0),
                              home_3b=int(r[52] or 0),home_hr=int(r[53] or 0),
                              away_manager=r[89].strip(),home_manager=r[91].strip()))
    games.sort(key=lambda g:(g['date'],g['game_num'],g['home'],g['away']))
    return games

def parse_regulation(linescore):
    if not linescore: return None
    vals=SCORE_RE.findall(linescore)
    if len(vals)<8: return None
    first=vals[:9]
    try: return sum(int(v[1:-1]) if v.startswith('(') else 0 if v.lower()=='x' else int(v) for v in first)
    except ValueError: return None

class TeamHistory:
    def __init__(self):
        self.games=deque(maxlen=60)
        self.last_date=None
        self.season_sum=[0,0,0]
    def summary(self,base,day):
        def rate(n,pos):
            x=list(self.games)[-n:]
            return (sum(v[pos] for v in x)+base*12)/(len(x)+12)
        n=self.season_sum[2]
        rest=3 if self.last_date is None else min(7,max(0,(day-self.last_date).days-1))
        return [rate(15,0),rate(15,1),rate(45,0),rate(45,1),
                (self.season_sum[0]+base*20)/(n+20),
                (self.season_sum[1]+base*20)/(n+20),rest,n]
    def record(self,day,scored,allowed):
        self.games.append((scored,allowed));self.last_date=day
        self.season_sum[0]+=scored;self.season_sum[1]+=allowed;self.season_sum[2]+=1

class PitcherHistory:
    def __init__(self):self.allowed=deque(maxlen=8)
    def summary(self,base):
        n=len(self.allowed)
        return [(sum(self.allowed)+base*4)/(n+4),n]
    def record(self,allowed):self.allowed.append(allowed)

def make_features(games):
    """Create pregame features using games from strictly earlier dates.

    All games scheduled on the same date are forecast before that date's
    results are added. This avoids leaking later or unknown same-day scores.
    """
    teams=defaultdict(TeamHistory);starters=defaultdict(PitcherHistory)
    season=None;league_runs=0;league_team_games=0
    X=[];out=[]
    from itertools import groupby
    for (year,day),group in groupby(games, key=lambda g:(g['year'],g['date'])):
        day_games=list(group)
        if year!=season:
            teams=defaultdict(TeamHistory);starters=defaultdict(PitcherHistory)
            league_runs=0;league_team_games=0;season=year
        base=(league_runs+4.45*500)/(league_team_games+500)
        for g in day_games:
            h=teams[g['home']].summary(base,day);a=teams[g['away']].summary(base,day)
            hs=starters[g['home_sp']].summary(base) if g['home_sp'] else [base,0]
            avs=starters[g['away_sp']].summary(base) if g['away_sp'] else [base,0]
            features=[h[0],a[0],h[1],a[1],h[2],a[2],h[3],a[3],
                      h[4],a[4],h[5],a[5],h[6],a[6],hs[0],avs[0],hs[1],avs[1],
                      h[7],a[7],base,day.month]
            assert len(features)==len(FEATURE_NAMES)
            X.append(features);out.append(g)
        for g in day_games:
            teams[g['home']].record(day,g['home_reg'],g['away_reg'])
            teams[g['away']].record(day,g['away_reg'],g['home_reg'])
            if g['home_sp']: starters[g['home_sp']].record(g['away_reg'])
            if g['away_sp']: starters[g['away_sp']].record(g['home_reg'])
            league_runs+=g['home_reg']+g['away_reg'];league_team_games+=2
    df=pd.DataFrame(X,columns=FEATURE_NAMES)
    df=pd.concat([pd.DataFrame(out).reset_index(drop=True),df],axis=1)
    return df

def model():
    return HistGradientBoostingRegressor(loss='poisson',max_iter=130,learning_rate=.055,
                                         max_leaf_nodes=11,min_samples_leaf=55,
                                         l2_regularization=7.0,random_state=42)

def train(train_df, features):
    home=model();away=model()
    x=train_df[features].to_numpy(dtype=float)
    home.fit(x,train_df.home_reg)
    away.fit(x,train_df.away_reg)
    return home,away

def preds(fit, df, features):
    X=df[features].to_numpy(dtype=float)
    return [np.clip(fit[0].predict(X),.3,14),np.clip(fit[1].predict(X),.3,14)]

def dispersion(means,actual):
    # NB variance = mu + alpha * mu^2. Use 2024 validation residuals only.
    excess=np.mean((np.asarray(actual)-np.asarray(means))**2-np.asarray(means))
    alpha=excess/np.mean(np.asarray(means)**2)
    return float(np.clip(alpha,0,.7))

@dataclass
class ExtraInnings:
    home_win: float
    extra_pmf: np.ndarray
    count: int

def extra_model(df):
    x=df[(df.home_reg==df.away_reg)&(df.home_final!=df.away_final)]
    if len(x)==0:raise ValueError('No extra-inning games in training sample')
    diff=(x.home_final+x.away_final-x.home_reg-x.away_reg).astype(int)
    # smoothed distribution on 1..16 additional runs; values above 16 grouped.
    hist=np.full(17,.5);hist[0]=0
    for v in diff:hist[min(max(int(v),1),16)]+=1
    hist/=hist.sum()
    return ExtraInnings(home_win=float(((x.home_final>x.away_final).sum()+2)/(len(x)+4)),extra_pmf=hist,count=len(x))

def run_pmf(mu,alpha,max_runs=35):
    k=np.arange(max_runs+1)
    p=poisson.pmf(k,mu) if alpha<.0002 else nbinom.pmf(k,1/alpha,1/(1+alpha*mu))
    p[-1]+=(1-p.sum())
    return p

def game_probs(muh,mua,ah,aa,extra):
    h=run_pmf(muh,ah);a=run_pmf(mua,aa)
    # Outer product index: visiting runs i, home runs j.
    mat=np.outer(a,h)
    i,j=np.indices(mat.shape)
    is_tie=i==j
    ph=float(mat[j>i].sum() + extra.home_win*mat[is_tie].sum())
    non_tie_under=float(mat[(~is_tie)&(i+j<=6)].sum())
    extras_cdf=np.cumsum(extra.extra_pmf)
    for score in range(4):
        budget=6-2*score
        if budget>=0:
            non_tie_under+=float(mat[score,score]*extras_cdf[min(budget,len(extras_cdf)-1)])
    return float(np.clip(ph,1e-6,1-1e-6)),float(np.clip(non_tie_under,1e-6,1-1e-6))

def metrics(y,p):
    y=np.asarray(y).astype(int);p=np.clip(np.asarray(p),1e-6,1-1e-6)
    bins=np.minimum((p*10).astype(int),9)
    ece=sum(np.mean(bins==b)*abs(np.mean(y[bins==b])-np.mean(p[bins==b]))
            for b in range(10) if np.any(bins==b))
    return dict(n=len(y),accuracy=float(np.mean((p>=.5)==y)),
                brier=float(np.mean((p-y)**2)),
                log_loss=float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))),
                ece_10=float(ece),mean_pred=float(np.mean(p)),actual_rate=float(np.mean(y)))

def paired_ci(y,model_prob,base_prob,seed=42):
    y=np.asarray(y).astype(float);p=np.asarray(model_prob);q=np.asarray(base_prob)
    d=(p-y)**2-(q-y)**2
    rng=np.random.default_rng(seed)
    sims=np.array([np.mean(d[rng.integers(0,len(d),len(d))]) for _ in range(1000)])
    return [float(np.percentile(sims,2.5)),float(np.percentile(sims,97.5))]

def eval_predictions(df,p_home,p_under,base_home,base_under):
    win=(df.home_final>df.away_final).to_numpy().astype(int)
    under=((df.home_final+df.away_final)<=6).to_numpy().astype(int)
    res={}
    for name,y,p,base in [('home_win',win,p_home,base_home),('under_6_5',under,p_under,base_under)]:
        res[name]={
            'model':metrics(y,p),'constant_baseline':metrics(y,np.full(len(y),base)),
            'brier_improvement_vs_baseline':float(np.mean((base-y)**2)-np.mean((np.asarray(p)-y)**2)),
            'brier_difference_model_minus_baseline_95pct_bootstrap_ci':paired_ci(y,p,np.full(len(y),base))}
    return res

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'data')
    ap.add_argument('--out-dir',type=Path,default=Path(__file__).parent/'results')
    ap.add_argument('--offline',action='store_true',help='Do not attempt to download missing data')
    ap.add_argument('--no-starter',action='store_true',help='Remove retrospective starter-identity proxy features')
    args=ap.parse_args()
    if not args.offline:download_logs(args.data_dir)
    games=read_rows(args.data_dir)
    df=make_features(games)
    train2023=df[df.year==2023].copy()
    val2024=df[df.year==2024].copy()
    train2024=df[df.year.isin([2023,2024])].copy()
    test2025=df[df.year==2025].copy()
    if min(len(train2023),len(val2024),len(test2025))<1500:
        raise ValueError('Unexpectedly few Retrosheet games per year; check files and parsing: '+str(df.groupby('year').size().to_dict()))
    features=[f for f in FEATURE_NAMES if not(args.no_starter and ('_sp_' in f))]
    fit23=train(train2023,features)
    valmean=preds(fit23,val2024,features)
    ah=dispersion(valmean[0],val2024.home_reg)
    aa=dispersion(valmean[1],val2024.away_reg)
    fit=train(train2024,features)
    mus=preds(fit,test2025,features)
    extras=extra_model(train2024)
    prob=np.array([game_probs(float(h),float(a),ah,aa,extras) for h,a in zip(*mus)])
    baseline_home=float((train2024.home_final>train2024.away_final).mean())
    baseline_under=float(((train2024.home_final+train2024.away_final)<=6).mean())
    stats=eval_predictions(test2025,prob[:,0],prob[:,1],baseline_home,baseline_under)
    stats['metadata']={'train_years':[2023,2024],'dispersion_validation_year':2024,'test_year':2025,
        'train_games':len(train2024),'test_games':len(test2025),
        'starter_proxy_included':not args.no_starter,
        'home_dispersion':ah,'away_dispersion':aa,
        'extra_inning_games_in_train':extras.count,
        'extra_inning_home_win_probability':extras.home_win,
        'training_constant_home_win':baseline_home,'training_constant_under_6_5':baseline_under,
        'warning':'Regular-season backtest only. No historical betting odds or 2026-game data. Starter proxy is actual starter retrospectively reported.'}
    args.out_dir.mkdir(parents=True,exist_ok=True)
    (args.out_dir/'metrics.json').write_text(json.dumps(stats,indent=2))
    results=test2025[['date','home','away','home_final','away_final']].copy()
    results['pred_home_win']=prob[:,0];results['pred_under_6_5']=prob[:,1]
    results['actual_home_win']=(test2025.home_final>test2025.away_final).astype(int)
    results['actual_under_6_5']=((test2025.home_final+test2025.away_final)<=6).astype(int)
    results.to_csv(args.out_dir/'holdout_predictions_2025.csv',index=False)
    print(json.dumps(stats,indent=2))
    print(f'Wrote {args.out_dir/"metrics.json"} and 2025 holdout predictions CSV')

if __name__=='__main__':main()
