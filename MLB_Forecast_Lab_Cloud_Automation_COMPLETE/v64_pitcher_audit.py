"""V6.4: transparent starter-vs-neutral scoring comparison.

Research-only: converts pre-game model outputs into an explainable regulation
run-rate breakdown. Never reads the game's final score or uses later results.
It is not a second predictor or a retrofit to a completed game's outcome.
"""
from __future__ import annotations
import math


def _safe_pos(v,label):
    try: x=float(v)
    except (TypeError,ValueError): raise ValueError(f"{label}: expected a number") from None
    if not math.isfinite(x) or x<=0: raise ValueError(f"{label}: must be finite positive")
    return x


def explain_starters(result):
    """Return regulation expected-run counterfactuals and model provenance.

    A rate per offense in this function includes the trained-model opponent SP
    features, optional V6.2 correction, postseason overlay, and neutral external
    park/lineup/weather assumptions.  It excludes walkoffs/extra innings; hence
    will not equal the average of the simulated *final* scores exactly.

    ``neutral`` replaces opponent-starter features with a common missing-data
    prior. This is NOT a calibrated causal statement about removing an ace.
    """
    adj=result.get('adjustments',{})
    adj_sp=adj.get('starter_total_rate',{})
    evidence=adj_sp.get('audit',{})
    if not all(k in evidence for k in ('home','away')):
        return {'available':False,'reason':'No starter adjustment audit available. Install V6.2+.'}
    post=adj.get('postseason_scoring',{})
    post_factor=_safe_pos(post.get('factor',1.0),'postseason factor')
    sim=result.get('simulation',{})
    park=_safe_pos(adj.get('park',{}).get('factor',1.0),'park factor')
    weather=_safe_pos(adj.get('weather',{}).get('factor',1.0),'weather factor')
    relief=adj.get('relief_rate_multiplier',{})
    persons=result.get('personnel',{})
    chosen_weight=float(adj_sp.get('weight',0.0))
    if not 0<=chosen_weight<=1:raise ValueError('Invalid calibration weight')
    sides={}
    for side in ('home','away'):
        a=evidence[side]
        neutral=_safe_pos(a['neutral_starter_rate'],f'{side} neutral rate')
        learned=_safe_pos(a['previously_learned_rate'],f'{side} learned rate')
        corrected=_safe_pos(a['adjusted_rate'],f'{side} calibrated rate')
        line=float(persons.get(side,{}).get('lineup_adjustment',{}).get('factor',1))
        relief_factor=float(relief.get(side,1.))
        if not math.isfinite(line*relief_factor) or line<=0 or relief_factor<=0:raise ValueError('Invalid scenario factors')
        scenario_factor=post_factor*park*weather*line*relief_factor
        sides[side]={
            'neutral_regulation_runs':neutral*scenario_factor,
            'learned_regulation_runs':learned*scenario_factor,
            'with_starter_regulation_runs':corrected*scenario_factor,
            'starter_learned_delta':(learned-neutral)*scenario_factor,
            'extra_calibration_delta':(corrected-learned)*scenario_factor,
            'starter_applied':bool(a.get('starter_applied',False)),
            'prior_starts':int(a.get('prior_starts_with_details',0)),
            'prior_era':float(a.get('prior_smoothed_era',0)),
            'projected_starter_innings':float(a.get('projected_opposing_starter_ip',0)),
            'scenario_factor':scenario_factor,
        }
    neutral_total=sum(sides[x]['neutral_regulation_runs'] for x in ('home','away'))
    learned_total=sum(sides[x]['learned_regulation_runs'] for x in ('home','away'))
    selected_total=sum(sides[x]['with_starter_regulation_runs'] for x in ('home','away'))
    if 'base_home_runs' in sim and 'base_away_runs' in sim:
        final_base=float(sim['base_home_runs'])+float(sim['base_away_runs'])
        expected_before_scenario=sum(float(adj_sp['audit'][x]['adjusted_rate']) for x in ('home','away'))*post_factor
        # Simulator's base rate is before lineup/park/weather. Do not silently
        # claim they are the same after scenario overlays.
        if abs(expected_before_scenario-final_base)>.035:
            return {'available':False,'reason':'Audit rates do not match simulator inputs. Check file versions and cached forecasts.'}
    return {
        'available':True,
        'sides':sides,
        'neutral_regulation_total':neutral_total,
        'learned_regulation_total':learned_total,
        'selected_regulation_total':selected_total,
        'pitcher_total_delta':selected_total-neutral_total,
        'learned_pitcher_total_delta':learned_total-neutral_total,
        'extra_calibration_total_delta':selected_total-learned_total,
        'calibration_weight':chosen_weight,
        'postseason_factor':post_factor,
        'note':'Regulation-only counterfactual based on model feature substitution; NOT a causal or exact-score estimate.'
    }
