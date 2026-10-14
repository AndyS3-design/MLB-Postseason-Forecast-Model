"""Fetch historical official postseason finals and validate an adaptive scoring prior.

Analysis only; writes research artifacts, NOT production predictions or weights.
Every historical forecast uses only completed earlier-day postseason games.
2026 is explicitly retrospective context, excluded from hyperparameter selection.
"""
from __future__ import annotations
import argparse,csv,json,math,time,zipfile
from collections import defaultdict
from datetime import date,timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

API='https://statsapi.mlb.com/api/v1/schedule'
GAME_TYPES='F,D,L,W'
POST_YEARS=tuple(range(2020,2027))
SIZES=(10,20,30,50,80,10**9)
STRENGTHS=(0.0,0.5,0.8,1.0,1.2)
LIMITS={'2026':date(2026,10,14)}


def retrieve(url,attempts=4):
    errors=[]
    for attempt in range(attempts):
        try:
            with urlopen(Request(url,headers={'User-Agent':'MLB Forecast Lab archival validation/1.0'}),timeout=55) as f:
                return json.load(f)
        except Exception as exc:
            errors.append(str(exc)[:150])
            if attempt+1<attempts:time.sleep(2+attempt*2)
    raise RuntimeError('Official MLB historical API unavailable: '+repr(errors))


def official_finals(year,cutoff,fetch=retrieve):
    begin=date(year,9,1)
    end=min(date(year,11,15),cutoff-timedelta(days=1))
    if end<begin:return []
    games={}
    left=begin
    while left<=end:
        right=min(left+timedelta(days=27),end)
        q=urlencode({'sportId':1,'startDate':left.isoformat(),'endDate':right.isoformat(),
                     'gameTypes':GAME_TYPES})
        payload=fetch(API+'?'+q)
        if not isinstance(payload,dict) or not isinstance(payload.get('dates'),list):
            raise ValueError('Bad MLB response for '+str(year))
        for day in payload['dates']:
            for g in day.get('games',[]):
                if g.get('gameType') not in GAME_TYPES:continue
                if g.get('status',{}).get('abstractGameState')!='Final':continue
                dt=date.fromisoformat(str(g.get('officialDate') or day.get('date'))[:10])
                if not begin<=dt<cutoff:continue
                try:
                    ident=str(int(g['gamePk']))
                    home=int(g['teams']['home']['score']);away=int(g['teams']['away']['score'])
                    if min(home,away)<0:raise ValueError('Negative runs')
                except (TypeError,KeyError,ValueError) as exc:
                    raise ValueError('Official final has missing ID/runs: '+str(g.get('gamePk'))) from exc
                record={'year':year,'date':dt.isoformat(),'game_id':ident,
                        'game_type':g['gameType'],'home_runs':home,
                        'away_runs':away,'total_runs':home+away}
                if ident in games and games[ident]!=record:
                    raise ValueError('Inconsistent duplicate game '+ident)
                games[ident]=record
        left=right+timedelta(days=1)
    return sorted(games.values(),key=lambda g:(g['date'],g['game_id']))


def regular_mean(root,year):
    data=Path(root)/'data'
    name=data/(f'GL{year}.TXT' if year>=2023 else f'gl{year}.zip')
    if not name.exists():raise FileNotFoundError('Missing Retrosheet regular-season data '+str(name))
    rows=[]
    if name.suffix=='.zip':
        with zipfile.ZipFile(name) as archive:
            files=[n for n in archive.namelist() if n.upper().endswith('.TXT') and '/__MACOSX/' not in n]
            if not files:raise ValueError('Missing game log in '+str(name))
            with archive.open(files[0]) as f:
                import io
                rows=list(csv.reader(io.TextIOWrapper(f,encoding='latin-1')))
    else:
        with name.open(newline='',encoding='latin-1') as f:
            rows=list(csv.reader(f))
    totals=[]
    for row in rows:
        try:
            if len(row)>=11 and row[0].startswith(str(year)):
                totals.append(int(row[9])+int(row[10]))
        except (TypeError,ValueError):continue
    if len(totals)<800:raise ValueError(f'Implausibly sparse {year} regular season ({len(totals)})')
    return {'year':year,'games':len(totals),'runs_per_game':sum(totals)/len(totals)}


def prior_ratio(prior,regular, current_year):
    completed=[y for y in range(max(2020,current_year-4),current_year) if y in prior and y in regular]
    if not completed:return None
    # Weight by the actual number of completed postseason games rather than
    # equally weighting a pandemic-era season and a full postseason.
    total_games=sum(len(prior[y]) for y in completed)
    runs=sum(g['total_runs'] for y in completed for g in prior[y])
    base=sum(regular[y]['runs_per_game']*len(prior[y]) for y in completed)/total_games
    return (runs/total_games)/base


def forecast_factor(ratio,regmean,prior_games,strength,prior_equiv):
    # In-season rates adapt only after earlier-DATE games have officially ended.
    if not prior_games:return 1+strength*(ratio-1)
    current=sum(g['total_runs'] for g in prior_games)/len(prior_games)/regmean
    weight=len(prior_games)/(len(prior_games)+prior_equiv)
    return 1+strength*((1-weight)*ratio+weight*current-1)


def validate(all_years,regular):
    metrics=[]
    for prior_eq in SIZES:
        for strength in STRENGTHS:
            by_year={}
            all_errors=[]
            for yr in range(2022,2026):
                if yr not in all_years:continue
                baseline=prior_ratio(all_years,regular,yr)
                if baseline is None:continue
                history=[]
                errors=[]
                for today in sorted({g['date'] for g in all_years[yr]}):
                    todays=[g for g in all_years[yr] if g['date']==today]
                    # All games on same day share the same previously completed
                    # sample; none of today's scores enter their own prediction.
                    adj=forecast_factor(baseline,regular[yr]['runs_per_game'],history,
                                        strength,prior_eq)
                    for g in todays:
                        expected=regular[yr]['runs_per_game']*adj
                        errors.append(abs(expected-g['total_runs']))
                    history.extend(todays)
                by_year[yr]={'n':len(errors),'mae':sum(errors)/len(errors)}
                all_errors.extend(errors)
            if all_errors:
                metrics.append({'prior_equivalent_games':prior_eq,'strength':strength,
                    'n':len(all_errors),'pooled_mae':sum(all_errors)/len(all_errors),
                    'by_year':by_year})
    metrics.sort(key=lambda r:(r['pooled_mae'],r['strength'],r['prior_equivalent_games']))
    return metrics


def evaluate_2026(post,regular,models):
    base=prior_ratio(post,regular,2026)
    if base is None or 2026 not in post:return []
    observed=[]
    for cfg in models:
        history=[]
        errors=[]
        factors=[]
        for dt in sorted({g['date'] for g in post[2026]}):
            todays=[g for g in post[2026] if g['date']==dt]
            factor=forecast_factor(base,regular[2026]['runs_per_game'],history,
                                   cfg['strength'],cfg['prior_equivalent_games'])
            for g in todays:
                errors.append(abs(regular[2026]['runs_per_game']*factor-g['total_runs']))
                factors.append(factor)
            history.extend(todays)
        observed.append({'prior_equivalent_games':cfg['prior_equivalent_games'],
                         'strength':cfg['strength'],'n':len(errors),
                         'pooled_mae':sum(errors)/len(errors),'mean_factor':sum(factors)/len(factors),
                         'next_factor':forecast_factor(base,regular[2026]['runs_per_game'],
                                                       post[2026],cfg['strength'],cfg['prior_equivalent_games'])})
    return observed


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--out',type=Path)
    ap.add_argument('--as-of-exclusive',default='2026-10-14')
    a=ap.parse_args()
    cutoff=date.fromisoformat(a.as_of_exclusive)
    root=a.root
    years={}
    for yr in POST_YEARS:
        end=min(cutoff,date(yr+1,1,1))
        games=official_finals(yr,end)
        if yr<=2025 and len(games)<30:
            raise ValueError(f'Incomplete {yr} official postseason ({len(games)} finals)')
        if games:years[yr]=games
        print('OFFICIAL POSTSEASON',yr,'games',len(games),flush=True)
    regular={yr:regular_mean(root,yr) for yr in range(2020,2026)}
    # The completed 2026 regular season file uses MLB official API scores.
    path=root/'data/mlb_2026_regular.csv'
    with path.open(newline='',encoding='utf-8-sig') as f:
        current=[r for r in csv.DictReader(f) if r.get('home_final') and r.get('away_final')]
    regular[2026]={'year':2026,'games':len(current),'runs_per_game':
                   sum(int(g['home_final'])+int(g['away_final']) for g in current)/len(current)}
    ranked=validate(years,regular)
    chosen=ranked[0]
    today=sorted(years.get(2026,[]),key=lambda x:(x['date'],x['game_id']))
    assess=evaluate_2026(years,regular,[chosen,
          {'prior_equivalent_games':10**9,'strength':0.8},
          {'prior_equivalent_games':20,'strength':0.8},
          {'prior_equivalent_games':30,'strength':1.0}])
    yearly=[]
    for yr,games in sorted(years.items()):
        mean=sum(g['total_runs'] for g in games)/len(games)
        reg=regular[yr]['runs_per_game']
        yearly.append({'year':yr,'post_games':len(games),'post_mean_total':round(mean,5),
            'regular_games':regular[yr]['games'],'regular_mean_total':round(reg,5),
            'post_to_regular_ratio':round(mean/reg,5)})
    output=a.out or root/'outputs/v13_postseason'
    output.mkdir(exist_ok=True,parents=True)
    with (output/'official_postseason_2020_2026.csv').open('w',newline='',encoding='utf-8') as f:
        fieldnames=['year','date','game_id','game_type','away_runs','home_runs','total_runs']
        writer=csv.DictWriter(f,fieldnames=fieldnames);writer.writeheader()
        for yr in years:writer.writerows(years[yr])
    details={'as_of_exclusive':cutoff.isoformat(),'source':'Official MLB Stats API final schedules and Retrosheet regular game logs',
        'training_years_for_hyperparameter_selection':list(range(2022,2026)),
        'evaluation_2026_role':'retrospective diagnostic only; 2026 outcomes already influenced earlier project development',
        'season_totals':yearly,'selection_method':'Chronological previous-season-only preseason ratio plus day-exclusive partial-year adaptation; MAE against actual per-team runs, 2022-25',
        'candidates':ranked,'selected_candidate':chosen,
        '2026_diagnostics_not_selection':assess,
        'no_hindsight_guard':'All in-season games strictly earlier DATE; 2026 excluded from parameter selection',
        'known_limitation':'Year-level run baseline is not equivalent to complete game-specific baseball model; production change requires separate game-specific and prospective validation.'}
    (output/'comparison.json').write_text(json.dumps(details,indent=2,allow_nan=False)+'\n')
    lines=['# Postseason runs: 2020–2026 official final-score study','',
      'Research only; 2026 games are **not** an untouched holdout. See JSON for all grid settings and per-year MAE.',
      '', '| Year | Games | Postseason combined runs/game | Regular combined runs/game | Post/reg |',
      '|---|---:|---:|---:|---:|']
    for y in yearly:lines.append(f"| {y['year']} | {y['post_games']} | {y['post_mean_total']:.3f} | {y['regular_mean_total']:.3f} | {y['post_to_regular_ratio']:.3f} |")
    lines.extend(['','Selected candidate on 2022–2025 game-level MAE with day-exclusive running data: '
                  +json.dumps({k:v for k,v in chosen.items() if k!='by_year'}),
                  '', '2026 retrospective diagnostics (never used for selection):',
                  '', '| Candidate | Games | MAE per team-run | Mean factor | Next factor |',
                  '|---|---:|---:|---:|---:|'])
    for item in assess:
        lines.append(f"| strength={item['strength']}, prior-equiv={item['prior_equivalent_games']} | {item['n']} | {item['pooled_mae']:.3f} | {item['mean_factor']:.3f} | {item['next_factor']:.3f} |")
    lines+=['','Do not scale past frozen forecasts or silently label this aggregate study a full matchup-model backtest.','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('RESULTS '+json.dumps({'selected':chosen,'annual':yearly,'diagnostics_2026':assess}),flush=True)

if __name__=='__main__':main()
