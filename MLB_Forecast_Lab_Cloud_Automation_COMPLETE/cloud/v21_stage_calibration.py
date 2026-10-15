"""Auditable, time-safe playoff-round scoring-bias calibration research.

Model selection: years 2021–2022, with only PRIOR season total-run labels.
Chronological holdout: 2023–2025 (retrospective, used in broader development).
2026 model backtest sensitivity is *diagnostic only*, never a tuning input.

The 2026 sensitivity rescales already-recorded expected runs ONLY: it does not
re-run the simulation or imply changed winner probabilities / 4.5 or 5.5 odds.
Do NOT overwrite saved originals or silently change production coefficients.
"""
from __future__ import annotations
import argparse,csv,json,math
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REGULAR_COMBINED={
    2020:9.291759465478842,2021:9.06134211609716,
    2022:8.566666666666666,2023:9.231275720164609,
    2024:8.786743515850145,2025:8.894650205761317,
}
EXPECTED={2020:53,2021:37,2022:40,2023:41,2024:43,2025:47}
ROUNDS={'F':'Wild Card','D':'Division Series','L':'Championship Series','W':'World Series'}
WEIGHTS=(0.,.25,.5,.75,1.)


def load_history(path=ROOT/'data/official_postseason_2020_2025.csv'):
    rows=[];ids=set()
    with Path(path).open(newline='',encoding='utf-8-sig') as f:
        for item in csv.DictReader(f):
            year=int(item['year']);gid=str(item['game_id'])
            code=item['game_type']
            total=int(item['total_runs'])
            if (year not in EXPECTED or code not in ROUNDS or total<0
                    or total!=int(item['away_runs'])+int(item['home_runs'])
                    or gid in ids):
                raise ValueError('Malformed or duplicate historical playoff final '+gid)
            ids.add(gid)
            rows.append({'year':year,'stage':code,'total':total,'game_id':gid})
    counts=Counter(r['year'] for r in rows)
    if dict(counts)!=EXPECTED:
        raise ValueError('2020–2025 complete postseason archive expected; found '+str(dict(counts)))
    return rows


def history_factor(history,year,stage,weight):
    """Stage correction relative to global prior. No target-or-later labels."""
    if stage not in ROUNDS or not 0<=weight<=1:raise ValueError('Invalid stage/weight')
    prior=[r for r in history if int(r['year'])<year and r['year'] in REGULAR_COMBINED]
    stage_prior=[r for r in prior if r['stage']==stage]
    if not stage_prior or len(prior)<30:
        raise ValueError('Missing before-season baseline for '+str(year))
    global_ratio=sum(r['total']/REGULAR_COMBINED[r['year']] for r in prior)/len(prior)
    stage_ratio=sum(r['total']/REGULAR_COMBINED[r['year']] for r in stage_prior)/len(stage_prior)
    return (1-weight)+weight*stage_ratio/global_ratio


def evaluate_league_history(history,years,weight):
    predictions=[]
    for year in years:
        past=[r for r in history if r['year']<year]
        global_ratio=sum(g['total']/REGULAR_COMBINED[g['year']] for g in past)/len(past)
        baseline=REGULAR_COMBINED[year]*global_ratio
        for g in history:
            if g['year']!=year:continue
            factor=history_factor(history,year,g['stage'],weight)
            pred=baseline*factor
            predictions.append((year,g['stage'],g['total'],baseline,pred))
    if not predictions:raise ValueError('No evaluation games')
    def err(k):return sum(abs(x[k]-x[2]) for x in predictions)/len(predictions)
    stages={}
    for stage in ROUNDS:
        sub=[r for r in predictions if r[1]==stage]
        stages[stage]={'n':len(sub),'mae':round(sum(abs(r[4]-r[2]) for r in sub)/len(sub),5)}
    return {'n':len(predictions),'mean_actual':round(sum(x[2] for x in predictions)/len(predictions),4),
        'baseline_mae':round(err(3),5),'candidate_mae':round(err(4),5),
        'candidate_bias':round(sum(x[4]-x[2] for x in predictions)/len(predictions),5),
        'by_round':stages}


def evaluate_v20_backtest(csv_path,history,selected):
    """Diagnostic model-mean shifts for 2026. Does not resimulate PMFs or win odds."""
    rows=[]
    with Path(csv_path).open(newline='',encoding='utf-8-sig') as f:
        for item in csv.DictReader(f):
            if item.get('round_code') not in ROUNDS:raise ValueError('Invalid replay playoff stage')
            year=int(str(item['date'])[:4])
            if year!=2026:raise ValueError('Mixed year research artifact')
            if item.get('model_version')!='18.0.0-forecast-integrity':
                raise ValueError('Incomparable V20 engine source version')
            original=float(item['expected_total_runs'])
            actual=int(item['actual_total_runs'])
            factor=history_factor(history,year,item['round_code'],selected)
            rows.append({'game_id':item['game_id'],'stage':item['round_code'],
                         'actual':actual,'original_mean':original,
                         'adjusted_mean':original*factor,'factor':factor})
    if len(rows)!=30 or len({r['game_id'] for r in rows})!=30:
        raise ValueError('Expected exactly 30 independent V20 game records')
    def score(sub):
        n=len(sub)
        return {'n':n,
          'actual_mean':round(sum(x['actual'] for x in sub)/n,4),
          'primary_mean':round(sum(x['original_mean'] for x in sub)/n,4),
          'candidate_mean':round(sum(x['adjusted_mean'] for x in sub)/n,4),
          'primary_mae':round(sum(abs(x['original_mean']-x['actual']) for x in sub)/n,5),
          'candidate_mae':round(sum(abs(x['adjusted_mean']-x['actual']) for x in sub)/n,5),
          'primary_signed_bias':round(sum(x['original_mean']-x['actual'] for x in sub)/n,5),
          'candidate_signed_bias':round(sum(x['adjusted_mean']-x['actual'] for x in sub)/n,5)}
    return {'all':score(rows),'by_round':{name:score([x for x in rows if x['stage']==name])
       for name in ('F','D','L')},
       'warning':'Mean-only counterfactual. A valid full-game forecast comparison needs independent paired raw simulations; winner Brier, total PMF and 4.5/5.5 odds are deliberately NOT estimated here.'}


def run(replay_csv=None,history_path=ROOT/'data/official_postseason_2020_2025.csv'):
    history=load_history(history_path)
    train={str(w):evaluate_league_history(history,(2021,2022),w) for w in WEIGHTS}
    selected=min(WEIGHTS,key=lambda w:(train[str(w)]['candidate_mae'],w))
    holdout={str(w):evaluate_league_history(history,(2023,2024,2025),w) for w in WEIGHTS}
    report={
        'scope':'2020–2025 official postseason scoring with fixed ahead-of-time stage-ratio experiments',
        'archive_games':len(history),'selected_weight_early_2021_2022_only':selected,
        'early_year_results':train,'later_year_results_not_used_for_selection':holdout,
        'holdout_rounds':holdout[str(selected)]['by_round'],
        '2026_used_for_selection':False,
        'policy':'Never change live scoring multipliers or frozen original forecasts from these data; evaluate raw paired simulator forecasts prospectively.',
        'limitations':[
          'Historical stage ratios are league-average total runs, not game-specific matchup forecasts.',
          '2023–25 have influenced prior model development, so the chronological holdout is not fully independent.',
          '2026 game labels are known and may only be evaluated after early-year coefficient selection.',
          'Do not use per-round postseason 2026 results to fit a round-specific multiplier.']
    }
    if replay_csv:
        report['retrospective_v20_2026_mean_only_sensitivity']=evaluate_v20_backtest(
            replay_csv,history,selected)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--v20-replay',type=Path)
    p.add_argument('--out',type=Path,default=ROOT/'outputs/v21_research/stage_calibration.json')
    args=p.parse_args()
    results=run(args.v20_replay)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    print('V21_MODEL_SELECTION',results['selected_weight_early_2021_2022_only'],flush=True)
    print('V21_HISTORICAL_TRAIN',json.dumps(results['early_year_results'],sort_keys=True),flush=True)
    print('V21_CHRONOLOGICAL_LATER_HOLDOUT',json.dumps(results['later_year_results_not_used_for_selection'],sort_keys=True),flush=True)
    if args.v20_replay:
        print('V21_2026_MEAN_ONLY_DIAGNOSTIC',
            json.dumps(results['retrospective_v20_2026_mean_only_sensitivity'],sort_keys=True),flush=True)
    print('V21_RESEARCH_ARTIFACT',args.out,flush=True)

if __name__=='__main__':main()
