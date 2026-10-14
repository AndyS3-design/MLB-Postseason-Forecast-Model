"""Reproducible ARCHIVAL-only postseason scoring-tail study.

This study does NOT fit game-specific MLB model coefficients. A season's
projection uses only completed PREVIOUS postseason seasons; no same-day
or current-season run totals enter the predictor.
"""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path

ALPHAS=(0.,.05,.10,.15,.20,.30,.40)
LINES=(3.5,4.5,5.5,6.5)
EXPECTED_GAMES={2020:53,2021:37,2022:40,2023:41,2024:43,2025:47}

def read_archive(path):
    byyear={}
    ids=set()
    with Path(path).open(newline='',encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            year=int(row['year']);ident=str(row['game_id'])
            runs=int(row['total_runs'])
            if year not in EXPECTED_GAMES or runs<0 or ident in ids:
                raise ValueError('Invalid/duplicate postseason scoring archive row')
            if int(row['away_runs'])+int(row['home_runs'])!=runs:
                raise ValueError('Inconsistent final score in '+ident)
            ids.add(ident)
            byyear.setdefault(year,[]).append(runs)
    if {yr:len(byyear.get(yr,[])) for yr in EXPECTED_GAMES}!=EXPECTED_GAMES:
        raise ValueError('Expected 261 unique completed MLB finals from 2020–2025')
    return byyear

def prob(k,mu,alpha):
    if k<0:return 0.
    if alpha==0:
        logp=k*math.log(mu)-mu-math.lgamma(k+1)
    else:
        size=1/alpha
        logp=(math.lgamma(k+size)-math.lgamma(size)-math.lgamma(k+1)+
              size*math.log(size/(size+mu))+k*math.log(mu/(size+mu)))
    return math.exp(logp)

def evaluate(byyear,years,alpha):
    predictions=[]
    for year in years:
        previous=[v for yr,x in byyear.items() if yr<year for v in x]
        if not previous:continue
        # Deliberately simple league average, not an ex-post same-season mean.
        mu=sum(previous)/len(previous)
        for runs in byyear[year]:
            p=max(1e-14,prob(runs,mu,alpha))
            thresholds={str(l):sum(prob(k,mu,alpha) for k in range(int(l)+1))
                        for l in LINES}
            predictions.append((runs,mu,-math.log(p),thresholds))
    n=len(predictions)
    return {'n':n,'alpha':alpha,'log_loss':round(sum(x[2] for x in predictions)/n,6),
            'mae_constant_mean':round(sum(abs(x[0]-x[1]) for x in predictions)/n,5),
            'brier_by_line':{str(line):round(sum(
                (x[3][str(line)]-int(x[0]<line))**2 for x in predictions)/n,6)
                for line in LINES},
            'predicted_mean':round(sum(x[1] for x in predictions)/n,4),
            'actual_mean':round(sum(x[0] for x in predictions)/n,4)}

def run(archive):
    games=read_archive(archive)
    train={str(a):evaluate(games,(2021,2022),a) for a in ALPHAS}
    selected=min(ALPHAS,key=lambda a:(train[str(a)]['log_loss'],a))
    holdout={str(a):evaluate(games,(2023,2024,2025),a) for a in ALPHAS}
    return {'scope':'ARCHIVAL AGGREGATE POSTSEASON SCORING STUDY ONLY',
        'season_counts':EXPECTED_GAMES,
        'train_years':[2021,2022],
        'retrospective_later_years':[2023,2024,2025],
        'selected_on_early_years_only':selected,
        'earlier_year_logloss_by_alpha':train,
        'later_year_comparison_by_alpha':holdout,
        'method':'Fixed previous-season-only mean, Poisson vs gamma-Poisson total-run likelihood (NB variance=mu+alpha*mu²).',
        'limitation':'These totals are NOT out-of-sample matchup-specific predictions; 2023–2025 scores informed broader project development. No change to production dispersion can be justified from this aggregate study alone.'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archive',type=Path,default=Path(__file__).resolve().parents[1]/'data/official_postseason_2020_2025.csv')
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'outputs/v17_research/distribution_study.json')
    a=p.parse_args()
    d=run(a.archive)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'selected_alpha':d['selected_on_early_years_only'],
                     'later_year_comparisons':d['later_year_comparison_by_alpha']},indent=2))
if __name__=='__main__':main()
