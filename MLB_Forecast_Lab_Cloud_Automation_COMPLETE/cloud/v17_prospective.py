"""Prospective full-distribution validation; NEVER retune on observed finals.

One original per game, strict timestamps, same cohort for baseline comparisons.
Reports every requested half-run threshold, calibration buckets and reliability.
All scores are computed from immutable original distribution fields.
"""
from __future__ import annotations
import math,random
from collections import defaultdict
from cloud.v8_evaluate import valid_original

LINES=(3.5,4.5,5.5,6.5)
BIN_EDGES=(0.,.2,.4,.6,.8,1.000001)


def _pmf(record):
    raw=record.get('total_distribution')
    if not isinstance(raw,dict) or not raw:return None
    try:
        p={int(k):float(v) for k,v in raw.items()}
        if any(v<0 or not math.isfinite(v) or k<0 for k,v in p.items()):return None
        if abs(sum(p.values())-1)>0.000001:return None
        if len(p)!=len(raw):return None
        return p
    except (TypeError,ValueError):return None


def _brier(probs,targets):
    return round(sum((p-y)**2 for p,y in zip(probs,targets))/len(probs),6)


def _calibration(probs,targets):
    bins=[]
    for lo,hi in zip(BIN_EDGES[:-1],BIN_EDGES[1:]):
        idx=[i for i,p in enumerate(probs) if lo<=p<hi]
        bins.append({'low':lo,'high':min(1.,hi),
                     'n':len(idx),
                     'predicted_mean':round(sum(probs[i] for i in idx)/len(idx),4) if idx else None,
                     'actual_frequency':round(sum(targets[i] for i in idx)/len(idx),4) if idx else None})
    return bins


def score_originals(originals):
    """Return neutral/unavailable explicitly when insufficient prospective data."""
    valid={}
    for item in originals:
        if (not isinstance(item,dict) or
                item.get('forecast_kind') not in ('original_pregame',None) or
                not valid_original(item)):
            continue
        gid=str(item.get('game_id',''))
        if gid in valid:
            # Never allow duplicate updated versions to inflate cohort size.
            raise ValueError('Multiple original forecasts for game '+gid)
        valid[gid]=item
    settled=[]
    excluded=defaultdict(int)
    for rec in valid.values():
        final=rec.get('official_final')
        if not final:continue
        try:
            home=int(final['home']);away=int(final['away'])
            if home<0 or away<0 or home==away:raise ValueError('invalid final')
        except (KeyError,TypeError,ValueError):
            excluded['malformed_final']+=1
            continue
        pmf=_pmf(rec)
        if pmf is None:
            excluded['missing_or_invalid_full_distribution']+=1
            continue
        total=home+away
        try:
            wp=float(rec['predicted_home_win'])
            expected=float(rec['expected_runs']['total'])
            elo=float(rec['elo_home_win'])
        except (KeyError,ValueError,TypeError):
            excluded['missing_numeric_forecast']+=1
            continue
        if not all(math.isfinite(v) for v in (wp,expected,elo)) or not(0<=wp<=1 and 0<=elo<=1):
            excluded['invalid_numeric_forecast']+=1
            continue
        settled.append((rec,home,away,total,pmf,wp,expected,elo))
    n=len(settled)
    result={'status':'awaiting_30_plus_frozen_originals' if n<30 else 'prospective_distribution_diagnostic',
            'unique_originals':len(valid),'settled_distribution_complete_games':n,
            'excluded':dict(excluded),
            'warning':'Small samples and past model selection do not establish calibration or a betting advantage.'}
    if n==0:return result
    winners=[int(home>away) for _,home,away,*_ in settled]
    preds=[x[5] for x in settled]
    elo=[x[7] for x in settled]
    obs=[x[3] for x in settled]
    exp=[x[6] for x in settled]
    result['winner']={'brier':_brier(preds,winners),'elo_brier_same_games':_brier(elo,winners),
                      'calibration':_calibration(preds,winners)}
    deltas=[(pr-yy)**2-(ee-yy)**2 for pr,ee,yy in zip(preds,elo,winners)]
    result['winner']['brier_delta_vs_elo']=round(sum(deltas)/n,6)
    by_day=defaultdict(list)
    for idx,row in enumerate(settled):
        by_day[str(row[0].get('date') or 'unknown')].append(deltas[idx])
    # Resampling calendar days preserves within-day game correlation. Do NOT
    # attach a confidence interval to a one-series/single-day comparison.
    if n>=30 and len(by_day)>=10:
        days=sorted(by_day);rng=random.Random(1701);draws=[]
        for _ in range(2000):
            chosen=[rng.choice(days) for _ in days]
            values=[v for day in chosen for v in by_day[day]]
            draws.append(sum(values)/len(values))
        draws.sort()
        result['winner']['paired_date_bootstrap_95_delta_vs_elo']=[
            round(draws[49],6),round(draws[1949],6)]
    else:
        result['winner']['paired_date_bootstrap_95_delta_vs_elo']=None
    result['winner']['paired_date_bootstrap_note']='Positive delta favors Elo. Only shown after at least 30 games on 10 dates; retrospective development history limits causal claims.'
    result['combined_runs']={'mae':round(sum(abs(a-b) for a,b in zip(exp,obs))/n,5),
                             'signed_bias':round(sum(a-b for a,b in zip(exp,obs))/n,5),
                             'mean_forecast':round(sum(exp)/n,5),
                             'mean_actual':round(sum(obs)/n,5)}
    lines={}
    for line in LINES:
        prob=[sum(p for k,p in row[4].items() if k<line) for row in settled]
        true=[int(x<=line) for x in obs]
        lines[f'{line:.1f}']={'n':n,'under_brier':_brier(prob,true),
            'under_forecast_mean':round(sum(prob)/n,5),
            'actual_under_frequency':round(sum(true)/n,5),
            'calibration':_calibration(prob,true)}
    result['total_lines']=lines
    versions=defaultdict(int)
    for row in settled:versions[str(row[0].get('model_version','unknown'))]+=1
    result['model_versions']=dict(sorted(versions.items()))
    result['comparability_note']='Version cohorts are disclosed; pooled metrics mix versions and are not an A/B test.'
    return result
