"""Hard 90%-win-accuracy acceptance gate for the FULL 2026 postseason.

Evidence is explicitly retrospective until genuinely timestamped originals
exist. Reject duplicate games, missing results, incorrect record versions
and any in-sample attempt to label tuned historical performance as live skill.
"""
from __future__ import annotations
import argparse,csv,json,math
from datetime import date
from pathlib import Path

TARGET=.90
EXPECTED_N=30
CUTOFF=date(2026,10,15)
REPLAY_VERSION='18.0.0-forecast-integrity'


def wilson(k,n):
    if n<=0:return None
    z=1.96
    p=k/n
    den=1+z*z/n
    m=(p+z*z/(2*n))/den
    d=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(max(0,m-d),4),round(min(1,m+d),4)]


def evaluate(rows):
    rows=list(rows);ids=set()
    if len(rows)!=EXPECTED_N:raise ValueError(f'Expected all {EXPECTED_N} completed 2026 postseason games, got {len(rows)}')
    info=[]
    for r in rows:
        gid=str(r['game_id'])
        if gid in ids:raise ValueError('Duplicate game '+gid)
        ids.add(gid)
        if (r['model_version']!=REPLAY_VERSION or
                not date(2026,9,29)<=date.fromisoformat(r['date'])<CUTOFF or
                str(r['pregame_features_cutoff_exclusive'])!=str(r['date'])):
            raise ValueError('Bad engine, date, or no-leakage cutoff for '+gid)
        home=int(r['actual_home_runs']);away=int(r['actual_away_runs'])
        if min(home,away)<0 or home==away:raise ValueError('Invalid final '+gid)
        p=float(r['home_win_probability']);e=float(r['elo_home_win_probability'])
        o4=float(r['p_over_4_5']);o5=float(r['p_over_5_5'])
        combo4=float(r['p_pick_win_and_over_4_5']);combo5=float(r['p_pick_win_and_over_5_5'])
        if any(not math.isfinite(q) or q<0 or q>1 for q in (p,e,o4,o5,combo4,combo5)):
            raise ValueError('Invalid probability '+gid)
        if combo4>max(p,1-p)+1e-6 or combo5>max(p,1-p)+1e-6:
            raise ValueError('Impossible joint probability '+gid)
        y=int(home>away);total=home+away
        info.append({'game_id':gid,'date':r['date'],
          'model_win_correct':int((p>=.5)==bool(y)),
          'elo_win_correct':int((e>=.5)==bool(y)),
          'model_confidence':max(p,1-p),
          'elo_confidence':max(e,1-e),
          'model_brier':(p-y)**2,'elo_brier':(e-y)**2,
          'over_4_5_hit':int(total>=5),
          'over_5_5_hit':int(total>=6),
          'model_plus_over_4_5_hit':int((p>=.5)==bool(y) and total>=5),
          'model_plus_over_5_5_hit':int((p>=.5)==bool(y) and total>=6),
          'joint_probability_4_5':combo4,'joint_probability_5_5':combo5})
    n=len(info)
    picked=sum(x['model_win_correct'] for x in info)
    simple=sum(x['elo_win_correct'] for x in info)
    accuracy=picked/n
    target_wins=math.ceil(TARGET*n)
    thresholds={}
    for model,conf,right in (('primary','model_confidence','model_win_correct'),
                             ('elo','elo_confidence','elo_win_correct')):
        thresholds[model]={}
        for t in (.5,.55,.575,.6):
            selected=[x for x in info if x[conf]>=t]
            count=len(selected);hits=sum(x[right] for x in selected)
            thresholds[model][str(t)]={'n':count,
                'coverage':round(count/n,4),
                'correct':hits,
                'accuracy':round(hits/count,4) if count else None,
                'wilson95':wilson(hits,count)}
    def mean(key):
        return round(sum(x[key] for x in info)/n,6)
    return {'kind':'2026_full_postseason_retrospective_audit_not_prospective_accuracy',
       'sample_size':n,'target_fraction':TARGET,
       'target_wins_at_this_sample_size':target_wins,
       'winner_correct':picked,'winner_accuracy':round(accuracy,4),
       'winner_wilson_95':wilson(picked,n),
       'more_correct_winners_needed':max(0,target_wins-picked),
       'retrospective_90pct_numeric_threshold_met':picked>=target_wins,
       'can_claim_forward_accuracy_90pct':False,
       'reason_no_forward_claim':'Retrospective replay from a model developed after outcomes became known is never prospective validation.',
       'elo_winners_correct':simple,
       'model_brier':mean('model_brier'),'elo_brier':mean('elo_brier'),
       'actual_over_4_5_games':sum(x['over_4_5_hit'] for x in info),
       'actual_over_5_5_games':sum(x['over_5_5_hit'] for x in info),
       'model_pick_plus_over_4_5_hits':sum(x['model_plus_over_4_5_hit'] for x in info),
       'model_pick_plus_over_5_5_hits':sum(x['model_plus_over_5_5_hit'] for x in info),
       'mean_joint_winner_over_4_5':mean('joint_probability_4_5'),
       'mean_joint_winner_over_5_5':mean('joint_probability_5_5'),
       'confidence_filter_diagnostics_not_optimized_for_2026':thresholds,
       'caveat':'No in-sample threshold search, memorized score lookups or cherry-picked game omissions count toward the 90% all-game goal.'}


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--replay',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    q=a.parse_args()
    with q.replay.open(newline='',encoding='utf-8-sig') as f:report=evaluate(csv.DictReader(f))
    q.out.parent.mkdir(parents=True,exist_ok=True)
    q.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('V22_90PCT_GOAL_AUDIT',json.dumps(report,sort_keys=True),flush=True)

if __name__=='__main__':main()
