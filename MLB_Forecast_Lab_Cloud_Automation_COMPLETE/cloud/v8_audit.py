"""Research-only 2026 playoff replay. NOT independent, prospective validation.
No game-day outcomes, postgame starter IDs, or postgame lineups are supplied as
predictive inputs; same-day and future games are excluded for every matchup.
"""
import argparse,csv,json,time
from pathlib import Path
import numpy as np
from extended_eval import all_games
from v4_workflow import build_assets,generate
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only

def completed_games(data,cutoff):
    with (data/'mlb_postseason_2023_2026.csv').open(newline='',encoding='utf-8-sig') as f:
        source=list(csv.DictReader(f))
    rows=[r for r in source if r['year']=='2026' and r['date']<cutoff
          and r['away_final']!='' and r['home_final']!='']
    rows.sort(key=lambda r:(r['date'],r['first_pitch_utc'],r['game_id']))
    assert len(set(r['game_id'] for r in rows))==len(rows)
    return rows

def metrics(rows,postseason=True):
    if not rows:return {'n':0}
    k='' if postseason else 'no_post_'
    p=np.array([float(x[k+'home_win']) for x in rows]); u=np.array([float(x[k+'under']) for x in rows])
    total=np.array([float(x[k+'total']) for x in rows])
    y=np.array([int(x['home_won']) for x in rows]); t=np.array([int(x['actual_total']) for x in rows])
    return {'n':len(rows),'winner_accuracy':round(float(np.mean((p>=.5)==y)),4),
        'winner_brier':round(float(np.mean((p-y)**2)),5),
        'under_6_5_brier':round(float(np.mean((u-(t<=6))**2)),5),
        'total_mae':round(float(np.mean(np.abs(total-t))),4),
        'mean_predicted_total':round(float(np.mean(total)),3),
        'mean_actual_total':round(float(np.mean(t)),3)}

def audit(root,cutoff='2026-10-13',simulations=12000):
    start=time.monotonic();root=Path(root);data=root/'data';actual=completed_games(data,cutoff)
    if not actual:raise ValueError('No completed postseason games before selected cutoff')
    history=all_games(data,True);assets=build_assets(history,root)
    years=assets['training_years']
    if years!=list(range(2016,2026)):
        raise ValueError(f'Incomplete historical training years: {years}')
    prior_by_date={};records=[]
    for index,game in enumerate(actual,1):
        day=game['date']
        if day not in prior_by_date:
            prior=pregame_history_only(history,day)
            assert all(str(g['date'])[:10]<day for g in prior)
            prior_by_date[day]=(prior,historical_cutoff_assets(assets,day))
        prior,a=prior_by_date[day]
        clean=clean_game_input({'id':game['game_id'],'date':day,'home':game['home'],
            'away':game['away'],'game_type':game['game_type']},verified_pregame=False)
        assert 'home_final' not in clean and 'away_final' not in clean
        def make(post):
            return generate(prior,root,day,clean,assets=a,n=simulations,
                official_snapshot=None,postseason_context_enabled=post,include_2026_snapshot=post)
        full=make(True);neutral=make(False);f=full['forecast'];b=neutral['forecast']
        home=int(game['home_final']);away=int(game['away_final'])
        row={'game_id':game['game_id'],'date':day,'stage':game['game_type'],
             'away':game['away'],'home':game['home'],'actual_away':away,'actual_home':home,
             'actual_total':home+away,'home_won':int(home>away),
             'home_win':float(f['home_win_probability']),
             'under':float(f['under_6_5_probability']),'total':float(f['total_expected_runs']),
             'expected_away':float(f['away_expected_runs']),'expected_home':float(f['home_expected_runs']),
             'elo_home_win':float(full['baseline']['elo_home_win']),
             'no_post_home_win':float(b['home_win_probability']),
             'no_post_under':float(b['under_6_5_probability']),
             'no_post_total':float(b['total_expected_runs']),
             'postseason_factor':float(full['adjustments']['postseason_scoring']['factor']),
             'uses_oct_2026_snapshot':bool(full['adjustments']['postseason_scoring'].get('current_2026_snapshot_used',False)),
             'starter_policy':'no independently archived pregame starter ID; omitted',
             'features_cutoff_exclusive':day,'training_years':'2016-2025'}
        records.append(row)
        print(f"AUDIT {index}/{len(actual)} {day} {game['away']}@{game['home']} actual={away}-{home} expected={row['total']:.2f} P(home)={row['home_win']:.3f}",flush=True)
    f=metrics(records);b=metrics(records,False)
    elo=np.array([r['elo_home_win'] for r in records]);y=np.array([r['home_won'] for r in records])
    with (data/'mlb_postseason_2023_2026.csv').open(newline='',encoding='utf-8-sig') as fd:
        prior=[r for r in csv.DictReader(fd) if r['year']=='2025' and r['away_final']!='' and r['home_final']!='']
    prior_tot=np.array([int(r['away_final'])+int(r['home_final']) for r in prior])
    t=np.array([r['actual_total'] for r in records])
    summary={'type':'RETROSPECTIVE_NOT_UNTOUCHED','as_of_exclusive':cutoff,
        'games_evaluated':len(records),'years_loaded':years,'simulations_per_game':simulations,
        'postseason_context':f,'without_postseason_context':b,
        'elo_home_brier':round(float(np.mean((elo-y)**2)),5),
        'elo_winner_accuracy':round(float(np.mean((elo>=.5)==y)),4),
        'constant_50pct_home_brier':.25,
        'historical_2025_postseason_baseline':{
          '2025_mean_total':round(float(np.mean(prior_tot)),3),
          '2025_under_6_5_rate':round(float(np.mean(prior_tot<=6)),4),
          '2026_total_mae':round(float(np.mean(np.abs(t-np.mean(prior_tot)))),4),
          '2026_under_6_5_brier':round(float(np.mean((np.mean(prior_tot<=6)-(t<=6))**2)),5)},
        'by_round':{c:metrics([r for r in records if r['stage']==c]) for c in 'FDLW'
                    if any(r['stage']==c for r in records)},
        'runtime_seconds':round(time.monotonic()-start,2),
        'limitations':[
          '2026 games were seen during model development: this is retrospective research, not independent validation.',
          'No verified archived pregame starter identities or lineups exist for these games; strict replay omits them.',
          'The optional 2026 postseason scoring snapshot shares some 2026 outcomes and is applied only starting October 12.',
          'Do not optimize model coefficients on this sample and then call its error a holdout.',
          'Prospective claims require timestamped first-pitch-locked forecasts, many settled games, and uncertainty intervals.']}
    return summary,records

def write_results(out,summary,rows):
    out=Path(out);out.mkdir(exist_ok=True,parents=True)
    (out/'postseason_2026_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (out/'postseason_2026_game_replays.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    a=summary['postseason_context'];b=summary['without_postseason_context']
    lines=['# 2026 MLB Postseason — Retrospective Forecast Audit','',
        '**Research replay, not independent validation.** 2026 outcomes have influenced earlier model development. Starter names and lineups verified only after games are excluded.','',
        f"Games: **{summary['games_evaluated']}**; model training: **2016–2025**; {summary['simulations_per_game']:,} simulations per game. Before **{summary['as_of_exclusive']}** (exclusive).",'',
        '| Metric | With playoff context | Without playoff context |','|---|---:|---:|',
        f"| Winner accuracy | {a['winner_accuracy']:.1%} | {b['winner_accuracy']:.1%} |",
        f"| Winner Brier (lower better) | {a['winner_brier']:.5f} | {b['winner_brier']:.5f} |",
        f"| Under 6.5 Brier (lower better) | {a['under_6_5_brier']:.5f} | {b['under_6_5_brier']:.5f} |",
        f"| Total MAE (lower better) | {a['total_mae']:.3f} | {b['total_mae']:.3f} |",
        f"| Mean projected total | {a['mean_predicted_total']:.2f} | {b['mean_predicted_total']:.2f} |",
        f"| Actual mean total | {a['mean_actual_total']:.2f} | {b['mean_actual_total']:.2f} |",
        '',f"**Elo winner accuracy:** {summary['elo_winner_accuracy']:.1%}; **Elo Brier:** {summary['elo_home_brier']:.5f}; **50/50 Brier:** 0.25000.",
        '','## Per-game results','',
        '| Date | Game | Actual away–home | Mean total forecast | Home win chance | Winner correct? |',
        '|---|---|---:|---:|---:|:---:|']
    for r in rows:
        correct=(r['home_win']>=.5)==bool(r['home_won'])
        lines.append(f"| {r['date']} | {r['away']} @ {r['home']} | {r['actual_away']}–{r['actual_home']} | {r['total']:.2f} | {r['home_win']:.1%} | {'Yes' if correct else 'No'} |")
    lines+=['','## Limitations','']+['- '+v for v in summary['limitations']]
    lines+=['','Full probabilities and proof-of-cutoff fields are in the companion CSV.']
    (out/'POSTSEASON_2026_AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--out',type=Path)
    p.add_argument('--as-of-exclusive',default='2026-10-13')
    p.add_argument('--simulations',type=int,default=12000)
    args=p.parse_args();score,rows=audit(args.root,args.as_of_exclusive,args.simulations)
    destination=args.out or args.root/'outputs/v8_audit';write_results(destination,score,rows)
    print(json.dumps(score,indent=2));print('WROTE',destination,flush=True)
if __name__=='__main__':main()
