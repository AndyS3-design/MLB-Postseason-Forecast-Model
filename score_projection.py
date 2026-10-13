"""Experimental full-game MLB exact-score distribution.

Regular nine-inning runs use the frozen 2023-24 run model and 2024
validation overdispersion. Tied regulation games add extra runs according
 to the empirically fitted 2023-24 extra-run distribution; those extra runs
are all assigned to the extra-inning winner (a simplification, not a claim
about actual extra-inning play-by-play).

Optionally tilt the home/away allocation WITHIN each final-game total to
match the separately validated Elo home-win probability. Total-run marginal
probabilities are invariant under this tilt. This is a research visualization,
NOT a calibrated exact-score forecasting model or a wagering edge.
"""
from __future__ import annotations
from collections import defaultdict
import math
import numpy as np
from backtest import run_pmf


def _logistic(x):
    return 1 / (1 + np.exp(-np.clip(x, -60, 60)))


def raw_final_score_matrix(home_mu, away_mu, home_alpha, away_alpha, extras, max_reg_runs=26):
    """Index is [home final runs, away final runs]. No ties in returned matrix."""
    if not np.isfinite(home_mu) or not np.isfinite(away_mu) or min(home_mu, away_mu) <= 0:
        raise ValueError('Run means must be finite and positive')
    if not 0 <= extras.home_win <= 1:
        raise ValueError('Bad extra-inning home-win probability')
    h = run_pmf(float(home_mu), float(home_alpha), max_runs=max_reg_runs)
    a = run_pmf(float(away_mu), float(away_alpha), max_runs=max_reg_runs)
    extra = np.asarray(extras.extra_pmf, dtype=float)
    if len(extra) < 2 or np.any(extra < 0) or not np.isclose(extra.sum(), 1.0, atol=1e-6):
        raise ValueError('Invalid fitted extra-inning run distribution')
    max_extra = len(extra) - 1
    # The final element of run_pmf folds in right-tail mass, so results at the
    # top edge are approximations. Most games remain far from that edge.
    mat = np.zeros((max_reg_runs + max_extra + 1,)*2, dtype=float)
    reg = np.outer(h, a)
    mat[:max_reg_runs+1,:max_reg_runs+1] = reg
    np.fill_diagonal(mat[:max_reg_runs+1,:max_reg_runs+1], 0.)
    for tied_runs, mass in enumerate(np.diag(reg)):
        if mass <= 0: continue
        for extra_runs in range(1,len(extra)):
            pmass = mass * extra[extra_runs]
            # An explicit approximation: all net extra runs scored by winner.
            mat[tied_runs+extra_runs,tied_runs] += pmass * extras.home_win
            mat[tied_runs,tied_runs+extra_runs] += pmass * (1-extras.home_win)
    mat /= mat.sum()
    return mat


def _total_groups(mat):
    h,a=np.indices(mat.shape)
    totals=h+a
    won=h>a
    lost=h<a
    size=mat.shape[0]+mat.shape[1]-1
    home=np.bincount(totals[won],weights=mat[won],minlength=size)
    away=np.bincount(totals[lost],weights=mat[lost],minlength=size)
    return home,away,totals,won,lost


def align_winner_to_elo(mat, target_home_win):
    """Preserve probability of each total, align winner marginal to Elo.

    For a given final total, the relative weights of scores ON THE SAME
    winning side stay unchanged. This is a transparent probability-tilt,
    rather than falsely implying the run model independently predicts Elo.
    """
    target=float(target_home_win)
    if not np.isfinite(target) or not 0.01 <= target <= 0.99:
        raise ValueError('Elo probability must lie between 0.01 and 0.99')
    home,away,totals,won,lost=_total_groups(mat)
    both=(home>0)&(away>0)
    fixed=np.where(both,0,home).sum()
    movable=(home+away)[both].sum()
    if target < fixed-1e-8 or target>fixed+movable+1e-8:
        raise ValueError('Desired winner probability not representable')
    logit=np.log(np.maximum(home[both],1e-300))-np.log(np.maximum(away[both],1e-300))
    weights=(home+away)[both]
    lo,hi=-35.,35.
    for _ in range(65):
        mid=(lo+hi)/2
        achieved=fixed+np.sum(weights*_logistic(logit+mid))
        if achieved<target:lo=mid
        else:hi=mid
    desired_h=home.copy();desired_a=away.copy()
    desired_h[both]=weights*_logistic(logit+(lo+hi)/2)
    desired_a[both]=weights-desired_h[both]
    scaled=mat.copy()
    hw=desired_h/np.maximum(home,1e-300)
    aw=desired_a/np.maximum(away,1e-300)
    scaled[won] *= hw[totals[won]]
    scaled[lost] *= aw[totals[lost]]
    scaled/=scaled.sum()
    return scaled


def summarize_score_matrix(mat, favored_home=None, top_n=5):
    h,a=np.indices(mat.shape)
    win=h>a
    p_home=float(mat[win].sum())
    most=np.dstack(np.unravel_index(np.argsort(mat,axis=None)[::-1][:top_n],mat.shape))[0]
    top=[{'home_runs':int(i),'away_runs':int(j),'probability':float(mat[i,j])} for i,j in most]
    outcome={'home_win_probability':p_home,'away_win_probability':1-p_home,
        'expected_home_final':float((mat*h).sum()),
        'expected_away_final':float((mat*a).sum()),
        'under_6_5_probability':float(mat[h+a<=6].sum()),
        'top_scores':top,
        'score_matrix_sum':float(mat.sum())}
    if favored_home is None:favored_home=p_home>=.5
    mask=win if favored_home else (h<a)
    candidates=np.where(mask,mat,-1)
    k=int(np.argmax(candidates))
    ih,ia=np.unravel_index(k,mat.shape)
    outcome['representative_favorite_score']={'home_runs':int(ih),
        'away_runs':int(ia),'probability':float(mat[ih,ia])}
    return outcome


def project_score(home_mu,away_mu,home_alpha,away_alpha,extras,elo_home):
    raw=raw_final_score_matrix(home_mu,away_mu,home_alpha,away_alpha,extras)
    raw_home=float(raw[np.indices(raw.shape)[0]>np.indices(raw.shape)[1]].sum())
    adjusted=align_winner_to_elo(raw,elo_home)
    result=summarize_score_matrix(adjusted,favored_home=elo_home>=.5)
    result.update(elo_home_win_probability=float(elo_home),raw_run_model_home_win=raw_home,
                  calibration_note='Elo-aligned score allocation; totals remain from a weakly validated experimental run model. Tied regulation games use approximate extra-inning scoring.')
    return result
