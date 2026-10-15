"""Unified, vectorized MLB inning simulation. Winners and scores emerge together.

Explicit assumptions: gamma/Poisson scoring, approximate manager hooks,
team-independent offense shocks plus a shared environment shock, simplified extras.
NOT a validated pitch-by-pitch or player at-bat simulator.
"""
from __future__ import annotations
import hashlib,math
from functools import lru_cache
import numpy as np
from scipy.linalg import eigh_tridiagonal
from scipy.optimize import brentq
from scipy.special import betainc, ndtr
from scipy.stats import nbinom, skellam


def _positive(x,name):
    f=float(x)
    if not math.isfinite(f) or f<=0:raise ValueError(f'{name} must be finite and >0')
    return f


def _home_ninth_profile(starter_mean,starter_era,bullpen_era,order=32):
    """Deterministic distribution of the normalized ninth-inning rate.

    The starter duration is a clipped N(starter_mean, .9). Include the atoms
    at both clipping bounds as well as quadrature over the continuous part.
    Starters never reach the ninth under the simulator's eight-inning cap.
    """
    if starter_era==bullpen_era:
        return np.array([1/9]),np.array([1.])
    x,w=np.polynomial.legendre.leggauss(order)
    ip=2.5+(x+1)*(8-2.5)/2
    z=(ip-starter_mean)/.9
    weights=w*((8-2.5)/2)*np.exp(-z*z/2)/(.9*np.sqrt(2*np.pi))
    ip=np.r_[2.5,ip,8.]
    weights=np.r_[ndtr((2.5-starter_mean)/.9),weights,
                  ndtr((starter_mean-8)/.9)]
    weights/=weights.sum()
    ninth=bullpen_era/(9*bullpen_era+ip*(starter_era-bullpen_era))
    return ninth,weights


def _size_biased_environment(alpha_game,order=48):
    if not alpha_game:
        return np.array([1.]),np.array([1.])
    shape=1/alpha_game+1
    # Golub-Welsch yields normalized generalized Laguerre weights directly;
    # unlike raw polynomial weights these never overflow Gamma(shape).
    indices=np.arange(1,order,dtype=float)
    x,v=eigh_tridiagonal(2*np.arange(order,dtype=float),
                         np.sqrt(indices)*np.sqrt(shape+indices-1))
    weights=v[0]**2
    # Discard only numerically negligible quadrature components. Retaining
    # their enormous score tails would dominate runtime at alpha_game=1.
    keep=weights>1e-14
    return (x[keep]+shape)*alpha_game,weights[keep]


@lru_cache(maxsize=512)
def _calibrate_home_intensity(home_mean,away_mean,starter_mean,starter_era,
                              bullpen_era,alpha_team,alpha_game):
    """Convert expected *observed* regulation runs to a nine-inning intensity.

    For latent total L, the omitted runs have expectation
        L E[q G T_h P(H_8 > A_9 | G, T_h, T_a, q)].
    Multiplying a unit-mean gamma density by its variate size-biases its
    shape from k to k+1. Thus integrate size-biased G, and marginalize the
    size-biased home team shock analytically as a negative binomial. The
    away shock keeps its original distribution. This preserves dependence
    through G without fitting to additional Monte Carlo draws.
    """
    ninth,profile_weights=_home_ninth_profile(starter_mean,starter_era,bullpen_era)
    environment,environment_weights=_size_biased_environment(alpha_game)
    away_distributions=[]
    if alpha_team:
        # The away score does not depend on the unknown home intensity, so
        # compute its PMF once. Truncation costs at most 1e-12 probability
        # in each mixture component, including high-dispersion tails.
        for g in environment:
            mean=away_mean*g
            p=1/(1+alpha_team*mean)
            if alpha_team>=1e-6:
                limit=int(nbinom.isf(1e-12,1/alpha_team,p))
            else:
                # A Chernoff bound avoids NB quantiles with p rounded to 1
                # near zero dispersion. Evaluate its exact gamma/Poisson
                # log-MGF using log1p so the Poisson limit stays continuous.
                delta=9*np.sqrt(mean*(1+alpha_team*mean))+30*(1+alpha_team*mean)
                while True:
                    u=alpha_team*delta/(1+alpha_team*mean)
                    log_bound=np.log1p(u)/alpha_team-(mean+delta)*(
                        np.log1p(delta/mean)-np.log1p(u))
                    if log_bound<=np.log(1e-12):break
                    delta*=2
                limit=int(np.ceil(mean+delta))
            scores=np.arange(limit+1,dtype=float)
            # Recurrence in log space avoids subtracting huge log-gammas
            # when alpha_team approaches zero, and underflow at score zero.
            log_pmf=np.empty(limit+1)
            log_pmf[0]=-np.log1p(alpha_team*mean)/alpha_team
            log_pmf[1:]=log_pmf[0]+np.cumsum(
                np.log(mean)+np.log1p(alpha_team*scores[:-1])
                -np.log1p(alpha_team*mean)-np.log(scores[1:]))
            away_distributions.append((scores,np.exp(log_pmf)))

    def expected_runs(latent):
        omitted=0.
        for i,(g,w) in enumerate(zip(environment,environment_weights)):
            home_eight=latent*(1-ninth)*g
            if alpha_team:
                scores,pmf=away_distributions[i]
                # P(H_8 > a), with H's gamma shape increased by one.
                # 1-p written directly avoids cancellation for small alpha.
                scale=alpha_team*home_eight
                survival=betainc(scores[None,:]+1,1/alpha_team+1,
                                 (scale/(1+scale))[:,None])
                probability=survival@pmf
            else:
                probability=skellam.sf(0,home_eight,away_mean*g)
            omitted+=w*float(np.dot(profile_weights*ninth,probability))
        return latent*(1-omitted)

    # Even if every possible bottom ninth were omitted, innings 1-8 supply
    # this upper bracket. Its profile weights match the actual IP sampler.
    upper=home_mean/(1-float(np.dot(ninth,profile_weights)))
    latent=brentq(lambda x:expected_runs(x)-home_mean,home_mean,upper,xtol=1e-10)
    return float(latent),float(expected_runs(latent))


def play_games(home_mu,away_mu,n=30000,seed=42,home_starter=None,away_starter=None,
    home_bullpen=None,away_bullpen=None,home_manager_hook=5.,away_manager_hook=5.,
    home_lineup=1.,away_lineup=1.,park_factor=1.,weather_factor=1.,
    postseason=False,alpha_team=.15,alpha_game=.05,extra_max=18):
    """Simulate innings 1-9, conditional bottom ninth, then extras on ties.

    home/away μ are expected actual regulation runs from ONE scoring model.
    The home latent inning intensity accounts for skipped bottom ninths.
    No Elo probability override.
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
    latent_h,calibrated_home_mean=_calibrate_home_intensity(
        m_h,m_a,.7*float(sp_a.get('innings',5))+.3*away_manager_hook,
        float(e_sp_a),float(e_bp_a),float(alpha_team),float(alpha_game))
    shared=rng.gamma(1/alpha_game,alpha_game,n) if alpha_game else np.ones(n)
    team_h=rng.gamma(1/alpha_team,alpha_team,n) if alpha_team else np.ones(n)
    team_a=rng.gamma(1/alpha_team,alpha_team,n) if alpha_team else np.ones(n)
    runs_home=rng.poisson(rates_home*(latent_h*shared*team_h)[:,None])
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
          'latent_home_nine_inning_runs':latent_h,
          'calibrated_home_regulation_runs':calibrated_home_mean,
          'home_inning_exposure_policy':'observed regulation mean calibrated before conditional bottom ninth',
          'home_calibration_method':'deterministic quadrature approximation (48 environment, 32 profile nodes); size-biased gamma/negative-binomial mixture',
          'extra_innings_home_rate_policy':'scenario_home_runs / 9, with existing extra-inning scale',
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
    # Exact-score *mode*, unconditioned on the game's favorite. A specific
    # Dodgers-win score may be the most common single score even when the
    # Brewers win more simulated games in aggregate. Keep the older
    # winner-conditioned representative as separate metadata for research.
    # This is PRESENTATION only: simulations, win odds and totals are unchanged.
    pick=int(np.argmax(counts))
    score_for_display={'home':int(unique[pick,0]),'away':int(unique[pick,1]),
       'total':int(unique[pick,0]+unique[pick,1]),'probability':float(counts[pick]/n),
       'method':'highest probability exact final score across all simulations; may differ from model favorite'}
    # The winner-aligned exact mode is a DIFFERENT, explicitly conditional
    # presentation statistic: maximize P(exact score) subject to the overall
    # majority-win side winning. Never overwrite the unconditional exact mode.
    favorite_win_probability=p_home if winner_home else 1-p_home
    fav_joint=float(counts[best]/n)
    favorite_aligned_score={'home':int(unique[best,0]),'away':int(unique[best,1]),
        'probability':fav_joint,
        'conditional_probability':float(fav_joint/favorite_win_probability),
        'winner_side':'home' if winner_home else 'away',
        'method':'most likely exact score among outcomes where the overall model favorite wins'}
    # True JOINT markets from the SAME score draws. Do not multiply marginal
    # winner and Over probabilities: those events may be correlated. The
    # favorite is still defined ONLY by the total winner probability.
    home_wins=h>a
    away_wins=a>h
    favorite_wins=home_wins if winner_home else away_wins
    win_and_over_probabilities={}
    for line in (4.5,5.5):
        high=total>line
        home_and_over=float(np.mean(home_wins & high))
        away_and_over=float(np.mean(away_wins & high))
        aligned=float(np.mean(favorite_wins & high))
        win_and_over_probabilities[f'{line:.1f}']={
            'home_win_and_over':home_and_over,
            'away_win_and_over':away_and_over,
            'favorite_win_and_over':aligned,
            'favorite_side':'home' if winner_home else 'away',
            'over':float(np.mean(high)),
            'method':'exact joint event frequency from same simulated final scores'}
        if abs((home_and_over+away_and_over)-float(np.mean(high)))>1e-10:
            raise AssertionError('Winning sides must partition total-run Over outcomes')
    return dict(score_grid=score_grid, total_pmf=total_pmf, v6_display_score=score_for_display,
       representative_score={'home':int(unique[best,0]),'away':int(unique[best,1]),'probability':fav_joint},
       favorite_aligned_score=favorite_aligned_score,
       win_and_over_probabilities=win_and_over_probabilities,
       home_win_probability=p_home,away_win_probability=1-p_home,
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

