"""Unified, vectorized MLB inning simulation. Winners and scores emerge together.

Explicit assumptions: gamma/Poisson scoring, approximate manager hooks,
team-independent offense shocks plus a shared environment shock, simplified extras.
NOT a validated pitch-by-pitch or player at-bat simulator.
"""
from __future__ import annotations
import hashlib,math
import numpy as np


def _positive(x,name):
    f=float(x)
    if not math.isfinite(f) or f<=0:raise ValueError(f'{name} must be finite and >0')
    return f


def play_games(home_mu,away_mu,n=30000,seed=42,home_starter=None,away_starter=None,
    home_bullpen=None,away_bullpen=None,home_manager_hook=5.,away_manager_hook=5.,
    home_lineup=1.,away_lineup=1.,park_factor=1.,weather_factor=1.,
    postseason=False,alpha_team=.15,alpha_game=.05,extra_max=18):
    """Simulate innings 1-9, conditional bottom ninth, then extras on ties.

    home/away μ come from ONE scoring model. No Elo probability override.
    Contextual lineup/park/weather multipliers are unvalidated scenario changes.
    """
    if not 100<=int(n)<=250000:raise ValueError('n must be 100..250000')
    n=int(n)
    base_h=_positive(home_mu,'home_mu');base_a=_positive(away_mu,'away_mu')
    hm=_positive(home_lineup,'home lineup');am=_positive(away_lineup,'away lineup')
    pf=_positive(park_factor,'park factor');wf=_positive(weather_factor,'weather factor')
    if not 0<=alpha_team<=1 or not 0<=alpha_game<=1:raise ValueError('Invalid gamma dispersion')
    rng=np.random.default_rng(seed)
    # model-specific baseline rate; all modifiers explicit and bounded to avoid huge surprises.
    m_h=float(np.clip(base_h*hm*pf*wf,0.8,12))
    m_a=float(np.clip(base_a*am*pf*wf,0.8,12))
    sp_h=home_starter or {'innings':5.,'era':4.35}
    sp_a=away_starter or {'innings':5.,'era':4.35}
    bp_h=home_bullpen or {'era':4.35}
    bp_a=away_bullpen or {'era':4.35}
    # SP and bullpen opponent profiles shape timing across innings; they do not
    # double-count those effects in the learned *total* runs (normalize to m).
    sp_h_ip=np.clip(rng.normal(.7*float(sp_h.get('innings',5))+.3*home_manager_hook,.9,n),2.5,8)
    sp_a_ip=np.clip(rng.normal(.7*float(sp_a.get('innings',5))+.3*away_manager_hook,.9,n),2.5,8)
    e_sp_h=np.clip(float(sp_h.get('era',4.35))/4.35,.6,1.6)
    e_sp_a=np.clip(float(sp_a.get('era',4.35))/4.35,.6,1.6)
    e_bp_h=np.clip(float(bp_h.get('era',4.35))/4.35,.6,1.6)
    e_bp_a=np.clip(float(bp_a.get('era',4.35))/4.35,.6,1.6)
    inning=np.arange(1,10,dtype=float)[None,:]
    # Fraction of each inning affected by starter, e.g. 5.1 IP => 10% of sixth.
    f_h=np.clip(sp_h_ip[:,None]-(inning-1),0,1)
    f_a=np.clip(sp_a_ip[:,None]-(inning-1),0,1)
    # Visitors bat vs home staff; home bat vs visitor staff.
    rates_away=f_h*e_sp_h+(1-f_h)*e_bp_h
    rates_home=f_a*e_sp_a+(1-f_a)*e_bp_a
    rates_away/=rates_away.sum(axis=1,keepdims=True)
    rates_home/=rates_home.sum(axis=1,keepdims=True)
    shared=rng.gamma(1/alpha_game,alpha_game,n) if alpha_game else np.ones(n)
    team_h=rng.gamma(1/alpha_team,alpha_team,n) if alpha_team else np.ones(n)
    team_a=rng.gamma(1/alpha_team,alpha_team,n) if alpha_team else np.ones(n)
    runs_home=rng.poisson(rates_home*(m_h*shared*team_h)[:,None])
    runs_away=rng.poisson(rates_away*(m_a*shared*team_a)[:,None])
    final_away=runs_away.sum(axis=1)
    after_eight=runs_home[:,:8].sum(axis=1)
    # Bottom nine does not occur if home already leads after top nine.
    final_home=after_eight+np.where(after_eight>final_away,0,runs_home[:,8])
    extras=np.zeros(n,dtype=int)
    for ext in range(10,extra_max+1):
        ties=np.flatnonzero(final_home==final_away)
        if not len(ties):break
        extra_scale=.75 if postseason else 1.35  # no automatic runner in playoff extras
        away_10=rng.poisson(np.clip((m_a/9)*extra_scale*shared[ties]*team_a[ties],.005,8))
        # Home only bats if required; preserve appropriate walkoff score.
        home_10=rng.poisson(np.clip((m_h/9)*extra_scale*shared[ties]*team_h[ties],.005,8))
        final_away[ties]+=away_10
        final_home[ties]+=np.where(final_home[ties]>final_away[ties],0,home_10)
        extras[ties]+=1
    remaining=np.flatnonzero(final_home==final_away)
    if len(remaining):
        choose_home=rng.random(len(remaining))<.5
        final_home[remaining]+=choose_home.astype(int)
        final_away[remaining]+=(~choose_home).astype(int)
    return dict(home_final=final_home,away_final=final_away,reg_home=runs_home,
        reg_away=runs_away,extra_innings=extras,
        config={'n':n,'seed':seed,'base_home_runs':base_h,'base_away_runs':base_a,
          'scenario_home_runs':m_h,'scenario_away_runs':m_a,'postseason':bool(postseason),
          'extra_innings_policy':('no automatic runner' if postseason else 'automatic runner approximation'),
          'dispersion_team':alpha_team,'dispersion_environment':alpha_game})


def summarize(draws):
    h=draws['home_final'];a=draws['away_final'];n=len(h)
    if np.any(h==a):raise ValueError('Simulation returned final ties')
    vals=np.stack([h,a],axis=1)
    unique,counts=np.unique(vals,axis=0,return_counts=True)
    ids=np.argsort(-counts)[:7]
    # Score-by-score probability map, including both margins of the 10+ tail.
    # Used ONLY for visualizing this exact simulation, never as a new estimator.
    grid_home=np.minimum(h,10).astype(int)
    grid_away=np.minimum(a,10).astype(int)
    grid_counts=np.bincount(grid_home*11+grid_away,minlength=121).reshape(11,11)
    score_grid={'cells':(grid_counts/n).tolist(),'samples':int(n),'cap':10,
                'home_axis':'rows','away_axis':'columns'}
    p_home=float(np.mean(h>a))
    total=h+a
    possible, frequencies=np.unique(total,return_counts=True)
    total_pmf={str(int(k)):float(v/n) for k,v in zip(possible,frequencies)}
    # One representative exact score for the majority-win side; never force other outcomes.
    winner_home=p_home>=.5
    qualified=[i for i in range(len(unique)) if (unique[i,0]>unique[i,1])==winner_home]
    best=max(qualified,key=lambda i:counts[i]) if qualified else int(np.argmax(counts))
    # Report the most frequently simulated exact score for the favored winner.
    # The old display selected an outcome near the rounded *mean total*,
    # which can overstate the typical/most likely discrete scoreline.
    # This changes only PRESENTATION, never the run probabilities or simulations.
    pick=best
    score_for_display={'home':int(unique[pick,0]),'away':int(unique[pick,1]),
       'total':int(unique[pick,0]+unique[pick,1]),'probability':float(counts[pick]/n),
       'method':'most common simulated exact score among outcomes for the model favorite; not a guaranteed result'}
    return dict(score_grid=score_grid, total_pmf=total_pmf, v6_display_score=score_for_display, representative_score={'home':int(unique[best,0]),'away':int(unique[best,1]),'probability':float(counts[best]/n)},home_win_probability=p_home,away_win_probability=1-p_home,
       under_6_5_probability=float(np.mean(total<=6)),over_6_5_probability=float(np.mean(total>=7)),
       home_minus_1_5_probability=float(np.mean(h-a>=2)),away_plus_1_5_probability=float(np.mean(a-h>=-1)),
       home_expected_runs=float(np.mean(h)),away_expected_runs=float(np.mean(a)),
       total_expected_runs=float(np.mean(total)),
       total_80_range=[int(x) for x in np.percentile(total,[10,90])],
       home_80_range=[int(x) for x in np.percentile(h,[10,90])],
       away_80_range=[int(x) for x in np.percentile(a,[10,90])],
       modal_exact_scores=[dict(home=int(unique[i,0]),away=int(unique[i,1]),probability=float(counts[i]/n)) for i in ids],
       monte_carlo_95_half_width_pp=float(100*1.96*np.sqrt(p_home*(1-p_home)/n)),
       simulation_size=n,
       warnings=['Monte Carlo interval represents sampling only, not model uncertainty.',
            'Exact-score prediction is inherently uncertain; do not treat modal score as likely in absolute terms.',
            'Detailed player and weather effects are experimental, not validated trading edges.'])


def seed_for(game_key:str,model_version:str):
    return int.from_bytes(hashlib.sha256((game_key+'|'+model_version).encode()).digest()[:4],'big')
