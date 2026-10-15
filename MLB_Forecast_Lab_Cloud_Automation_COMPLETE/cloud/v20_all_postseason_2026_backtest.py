"""Every completed 2026 postseason game (Sept 29–Oct 14): V20 retrospective winner, totals and joint odds.

Uses only earlier DATE features per game; *never* pre-fills historical
lineups or probable pitchers from postgame endpoints. Official final scores
are fetched independently AFTER all five probability forecasts were made.
Historical results influenced V20 development. This is NOT prospective
validation, an official timestamped original, or a Kalshi market-price study.
"""
from __future__ import annotations

import csv
import json
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

import numpy as np

from extended_eval import all_games
from v4_workflow import build_assets,generate
from v6_replay import clean_game_input,historical_cutoff_assets
from v6_strength import pregame_history_only
from v6_baseball_totals import half_run_line_probabilities
from forecast_engine import TEAM_NAMES
from cloud.v13_postseason_study import official_finals
import v4_workflow

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'research_v20_all_2026_postseason'
# The MLB locally archived postseason records include 29 known game identities
# through October 13. We intentionally read ONLY the knowable schedule and
# team fields, NOT the final scores, as forecast inputs. The October 14
# Brewers at Dodgers game was completed after the local data file snapshot.
# The full 30-game coverage is checked independently against MLB official
# Final results AFTER all predictions have been made.
PLAYOFF_CUTOFF_EXCLUSIVE=date(2026,10,15)
N=12000
LINES=(4.5,5.5)
ROUND_MAP={'F':'Wild Card','D':'Division Series','L':'Championship Series','W':'World Series'}

def eligible_games():
    path=ROOT/'data'/'mlb_postseason_2023_2026.csv'
    seen={}
    with path.open(newline='',encoding='utf-8-sig') as fh:
        for g in csv.DictReader(fh):
            if str(g.get('year'))!='2026':continue
            day=str(g['date']);gid=str(g['game_id'])
            if day>=PLAYOFF_CUTOFF_EXCLUSIVE.isoformat():continue
            rnd=g['game_type']
            if rnd not in ROUND_MAP:raise ValueError('Unexpected postseason round '+rnd)
            row=(day,rnd,gid,g['away'],g['home'],TEAM_NAMES[g['away']],TEAM_NAMES[g['home']])
            if gid in seen and seen[gid]!=row:raise ValueError('Conflicting game identity '+gid)
            seen[gid]=row
    known='849811'
    if known in seen:raise ValueError('October 14 game exists already; remove manual schedule entry')
    seen[known]=('2026-10-14','L',known,'MIL','LAN',
                  TEAM_NAMES['MIL'],TEAM_NAMES['LAN'])
    games=tuple(sorted(seen.values(),key=lambda x:(x[0],x[2])))
    if len(games)!=30:
        raise ValueError('Expected 30 archived schedule identities through Oct 14; got '+str(len(games)))
    return games

GAMES=eligible_games()
IDS={g[2] for g in GAMES}

def official_all_postseason_finals():
    # Source fetched only AFTER every forecasting call, not as predictive
    # input to the estimator. Independent coverage guard catches absent or
    # duplicate official finals instead of silently scoring a shorter set.
    verified=official_finals(2026,PLAYOFF_CUTOFF_EXCLUSIVE)
    by_id={}
    for row in verified:
        gid=str(row['game_id'])
        if row['game_type'] not in ROUND_MAP:
            raise ValueError('Unexpected MLB postseason game type '+gid)
        if gid in by_id:raise ValueError('Duplicate official final '+gid)
        by_id[gid]={
          'game_id':gid,'official_date':row['date'],
          'home_final':int(row['home_runs']),'away_final':int(row['away_runs']),
          'game_type':row['game_type'],
          'source':'Official MLB Stats API final schedule / linescore'}
    if set(by_id)!=IDS:
        raise ValueError('ARCHIVE COVERAGE MISMATCH: official finals '+str(len(by_id))+
         ' vs local game identities '+str(len(IDS))+
         '; missing='+repr(sorted(set(by_id)-IDS))+
         '; stale='+repr(sorted(IDS-set(by_id))))
    for day,rnd,gid,*_ in GAMES:
        row=by_id[gid]
        if row['official_date']!=day or row['game_type']!=rnd:
            raise ValueError('Official date or round disagrees with archived pregame game '+gid)
    return by_id

def replay():
    root=ROOT
    history=all_games(root/'data',True)
    assets=build_assets(history,root)
    if assets['training_years']!=list(range(2016,2026)):
        raise ValueError('Unexpected training years: '+repr(assets['training_years']))
    prior_cache={}
    rows=[]
    for index,(day,round_code,gid,away,home,away_name,home_name) in enumerate(GAMES,1):
        series=(('ALCS' if away in ('CLE','TBA') or home in ('CLE','TBA') else 'NLCS') if round_code=='L' else ROUND_MAP[round_code])
        if day not in prior_cache:
            prior=pregame_history_only(history,day)
            if any(str(x['date'])[:10]>=day for x in prior):
                raise AssertionError('A same-date or later result leaked into features')
            prior_cache[day]=(prior,historical_cutoff_assets(assets,day))
        prior,filtered_assets=prior_cache[day]
        # Do not assert historical game-start times or lineup identities that
        # aren't archived from a genuine pregame source.
        match=clean_game_input({'id':gid,'date':day,'game_type':round_code,
           'home':home,'away':away,'home_name':home_name,'away_name':away_name},
           verified_pregame=False)
        collected=[]
        original=v4_workflow.play_games
        def capture_raw(**kwargs):
            drawn=original(**kwargs)
            collected.append(drawn)
            return drawn
        v4_workflow.play_games=capture_raw
        try:
            model=generate(prior,root,day,match,assets=filtered_assets,n=N,
              official_snapshot=None,official_lineup_history=None,
              postseason_context_enabled=True,include_2026_snapshot=True)
        finally:
            v4_workflow.play_games=original
        if len(collected)!=1:raise AssertionError('Unexpected simulation count')
        home_runs=collected[0]['home_final'];away_runs=collected[0]['away_final']
        total=home_runs+away_runs
        f=model['forecast']
        home_prob=float(np.mean(home_runs>away_runs))
        if abs(home_prob-f['home_win_probability'])>1e-12:
            raise ValueError('Recorded win probability differs from raw simulated draws')
        pick_home=home_prob>=.5
        pick_side='home' if pick_home else 'away'
        pick_team=home_name if pick_home else away_name
        pick_win=(home_runs>away_runs) if pick_home else (away_runs>home_runs)
        probabilities=half_run_line_probabilities(f['total_pmf'])
        alignment=f.get('favorite_aligned_score') or {}
        row={'game_id':gid,'series':series,'round':ROUND_MAP[round_code],'round_code':round_code,'date':day,
          'matchup':away_name+' at '+home_name,
          'away_abbr':away,'home_abbr':home,
          'model_version':model['model_version'],
          'is_retrospective':True,
          'pregame_features_cutoff_exclusive':day,
          'official_pregame_lineups_available':False,
          'historical_starting_pitchers_omitted':True,
          'postseason_prior_games_used':model['adjustments']['postseason_scoring'].get('current_prior_games_used'),
          'model_winner_pick':pick_team,
          'model_winner_side':pick_side,
          'win_probability':round(float(max(home_prob,1-home_prob)),6),
          'home_win_probability':round(home_prob,6),
          'elo_home_win_probability':round(float(model['baseline']['elo_home_win']),6),
          'expected_total_runs':round(float(f['total_expected_runs']),5),
          'favorite_aligned_exact_score':alignment,
          'unconditional_exact_score':f.get('v6_display_score'),
          'p_over_4_5':round(float(probabilities['4.5']['over']),6),
          'p_over_5_5':round(float(probabilities['5.5']['over']),6),
          'p_pick_win_and_over_4_5':round(float(np.mean(pick_win & (total>=5))),6),
          'p_pick_win_and_over_5_5':round(float(np.mean(pick_win & (total>=6))),6),
          'simulation_count':len(total)}
        # Exact draw-based two-way combo chances are model estimates,
        # NOT products of independent win and total-run probabilities.
        assert row['p_pick_win_and_over_5_5']<=row['p_over_5_5']+1e-6
        assert row['p_pick_win_and_over_4_5']<=row['win_probability']+1e-6
        rows.append(row)
        print('REPLAY_BEFORE_SCORE',index,len(GAMES),day,series,away,'at',home,
              'model_pick',pick_team,'p',row['win_probability'],
              'p_over4.5',row['p_over_4_5'],
              'p_over5.5',row['p_over_5_5'],flush=True)

    # Outcomes enter scope only after ALL probability forecasts have been
    # calculated and recorded. They are never passed into generate().
    finals=official_all_postseason_finals()
    for row in rows:
        f=finals[row['game_id']]
        row['actual_home_runs']=f['home_final']
        row['actual_away_runs']=f['away_final']
        row['actual_total_runs']=f['away_final']+f['home_final']
        row['actual_winner']=row['home_abbr'] if f['home_final']>f['away_final'] else row['away_abbr']
        row['actual_winner_name']=row['matchup'].split(' at ')[1] if f['home_final']>f['away_final'] else row['matchup'].split(' at ')[0]
        row['picked_winner_correct']=(row['model_winner_pick']==row['actual_winner_name'])
        row['total_absolute_error']=round(abs(row['expected_total_runs']-row['actual_total_runs']),5)
        home_hit=int(f['home_final']>f['away_final'])
        row['winner_brier']=(row['home_win_probability']-home_hit)**2
        row['elo_winner_brier']=(row['elo_home_win_probability']-home_hit)**2
        for line in LINES:
            key=str(line).replace('.','_')
            over=(row['actual_total_runs']>line)
            p=row['p_over_'+key]
            joined=row['picked_winner_correct'] and over
            joint_prob=row['p_pick_win_and_over_'+key]
            row['actual_over_'+key]=over
            row['model_over_'+key+'_pick']=(p>=.5)
            row['model_over_'+key+'_correct']=((p>=.5)==over)
            row['picked_winner_plus_over_'+key+'_hit']=bool(joined)
            row['brier_over_'+key]=(p-int(over))**2
            row['brier_winner_plus_over_'+key]=(joint_prob-int(joined))**2
        print('SCORED_OFFICIAL',row['date'],row['series'],row['game_id'],
             'actual',row['actual_away_runs'],row['actual_home_runs'],
             'winner_correct',row['picked_winner_correct'],
             'combo4.5',row['picked_winner_plus_over_4_5_hit'],
             'combo5.5',row['picked_winner_plus_over_5_5_hit'],flush=True)

    def metric(subset):
        n=len(subset)
        if not n:return {'n':0}
        m=lambda k:float(sum(float(x[k]) for x in subset)/n)
        return {'n':n,
          'winner_correct':sum(x['picked_winner_correct'] for x in subset),
          'winner_accuracy':round(m('picked_winner_correct'),4),
          'winner_brier':round(m('winner_brier'),6),
          'elo_brier_same_games':round(m('elo_winner_brier'),6),
          'expected_total_mae':round(m('total_absolute_error'),4),
          'mean_predicted_total':round(m('expected_total_runs'),4),
          'mean_actual_total':round(m('actual_total_runs'),4),
          'over_4_5_correct':sum(x['model_over_4_5_correct'] for x in subset),
          'over_5_5_correct':sum(x['model_over_5_5_correct'] for x in subset),
          'over_4_5_brier':round(m('brier_over_4_5'),6),
          'over_5_5_brier':round(m('brier_over_5_5'),6),
          'actual_over_4_5':sum(x['actual_over_4_5'] for x in subset),
          'actual_over_5_5':sum(x['actual_over_5_5'] for x in subset),
          'picked_winner_and_over_4_5_hits':sum(x['picked_winner_plus_over_4_5_hit'] for x in subset),
          'picked_winner_and_over_5_5_hits':sum(x['picked_winner_plus_over_5_5_hit'] for x in subset),
          'mean_model_joint_win_over_4_5':round(m('p_pick_win_and_over_4_5'),6),
          'mean_model_joint_win_over_5_5':round(m('p_pick_win_and_over_5_5'),6)}
    # Fixed prior-only postseason over-rate baselines; no 2026 game result
    # is included when constructing the reference forecast.
    with (root/'data'/'official_postseason_2020_2025.csv').open(newline='') as fh:
        prior_finals=[v for v in csv.DictReader(fh) if v['year']=='2025']
    if len(prior_finals)<30:raise ValueError('2025 postseason benchmark too small')
    prior_over={str(line):sum(int(v['total_runs'])>line for v in prior_finals)/len(prior_finals)
                for line in LINES}
    naive={}
    for line in LINES:
        key=str(line).replace('.','_')
        p=prior_over[str(line)]
        naive[str(line)]={
           'prior_2025_over_rate':round(p,6),
           'baseline_brier_2026':round(sum((p-int(v['actual_total_runs']>line))**2 for v in rows)/len(rows),6),
           'model_brier_2026':round(sum(v['brier_over_'+key] for v in rows)/len(rows),6)}
    # Paired score difference is more robust than announcing a high hit rate
    # from a retrospective development sample. Positive means model worse.
    diffs=[v['winner_brier']-v['elo_winner_brier'] for v in rows]
    rng=np.random.default_rng(20261015)
    pairs=np.asarray(diffs)
    boot=np.mean(rng.choice(pairs,(6000,len(pairs)),replace=True),axis=1)
    paired={'delta_model_minus_elo_brier':round(float(np.mean(pairs)),6),
            'naive_game_bootstrap_95pct':[
               round(float(np.percentile(boot,2.5)),6),
               round(float(np.percentile(boot,97.5)),6)],
            'warning':'Game resampling assumes independence; shared series and model development violate clean independent inference.'}
    report={'as_of_utc':datetime.now(timezone.utc).isoformat(),
       'type':'RETROSPECTIVE_FIXED_CURRENT_MODEL_NOT_PROSPECTIVE',
       'model_version':rows[0]['model_version'],
       'sample_size':len(rows),'simulations_per_game':N,
       'scope':'ALL 2026 postseason games through October 14 inclusive, official results verified for 30 unique games',
       'all_games':metric(rows),
       'by_round':{stage:metric([x for x in rows if x['round_code']==stage]) for stage in ('F','D','L')},
       '2025_postseason_total_market_baselines':naive,
       'paired_winner_vs_elo_uncertainty':paired,
       'by_series':{s:metric([x for x in rows if x['series']==s]) for s in ('ALCS','NLCS')},
       'game_rows':rows,
       'limitations':[
         '2026 postseason game outcomes were known during V20 development; this is retrospective and cannot validate an unseen trading edge.',
         'Historical starting pitchers and actual nine-player batting orders are OMITTED because no independent, timestamped pregame source is available for each past game.',
         'Source uses strictly earlier-date historical features and does NOT supply actual final scores until all five probability forecasts are complete.',
         'Kalshi closing odds, fees, fills and exact markets were not provided. No actual trading ROI or profitable edge is established.',
         'Winner+Over joint chances are measured DIRECTLY from shared individual simulations, not by multiplying marginal win and over chances.',
         'As of Oct 15, 30 completed playoff games through Oct 14 were included; Oct 15 games excluded from this cutoff.']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'all_postseason_2026_v20_metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    names=list(rows[0])
    with (OUT/'all_postseason_2026_v20_per_game.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:(json.dumps(v,sort_keys=True) if isinstance(v,dict) else v) for k,v in row.items()})
    table=['# All 2026 postseason games through Oct 14: current V20 retrospective replay','',
      '**Research replay only.** No postgame batting orders or pitcher identities were used as pregame predictors. Outcomes are verified independently from official MLB final-score feed *after* every forecast was calculated.','',
      '| Game | Actual away–home | Model winner | Win p | Winner hit | Over 4.5 p | O4.5 hit | Over 5.5 p | O5.5 hit | Pick + O4.5 hit | Pick + O5.5 hit |',
      '|---|---:|---|---:|:---:|---:|:---:|---:|:---:|:---:|:---:|']
    for x in rows:
        table.append(f"| {x['date']} {x['away_abbr']}@{x['home_abbr']} | {x['actual_away_runs']}–{x['actual_home_runs']} | {x['model_winner_pick']} | {x['win_probability']:.1%} | {'Yes' if x['picked_winner_correct'] else 'No'} | {x['p_over_4_5']:.1%} | {'Yes' if x['actual_over_4_5'] else 'No'} | {x['p_over_5_5']:.1%} | {'Yes' if x['actual_over_5_5'] else 'No'} | {'Yes' if x['picked_winner_plus_over_4_5_hit'] else 'No'} | {'Yes' if x['picked_winner_plus_over_5_5_hit'] else 'No'} |")
    a=report['all_games']
    table+=['',f"Winner picks: **{a['winner_correct']}/{a['n']}**. Model over 4.5 direction correct: **{a['over_4_5_correct']}/{a['n']}**; Over 5.5: **{a['over_5_5_correct']}/{a['n']}**.",
        f"Both winner pick + Over 4.5 correct: **{a['picked_winner_and_over_4_5_hits']}/{a['n']}**; winner pick + Over 5.5: **{a['picked_winner_and_over_5_5_hits']}/{a['n']}**.",
        f"Total-run MAE: {a['expected_total_mae']:.3f}; winner Brier: {a['winner_brier']:.4f}; Elo on same 30 games: {a['elo_brier_same_games']:.4f}.",
        '', '## Limitations','']+['- '+x for x in report['limitations']]
    table += ['', '## Metrics by round', '',
       '| Round | n | Winner right | Over 4.5 right | Over 5.5 right | Winner + O4.5 hits | Winner + O5.5 hits |',
       '|---|---:|---:|---:|---:|---:|---:|']
    for stage,entry in report['by_round'].items():
        table.append(f"| {ROUND_MAP[stage]} | {entry['n']} | {entry['winner_correct']} | {entry['over_4_5_correct']} | {entry['over_5_5_correct']} | {entry['picked_winner_and_over_4_5_hits']} | {entry['picked_winner_and_over_5_5_hits']} |")
    table += ['', '## Independent comparison baselines', '',
       'Model minus Elo winner Brier: '+str(paired['delta_model_minus_elo_brier'])+'; naive 95% bootstrap interval: '+str(paired['naive_game_bootstrap_95pct'])+'.',
       'Prior-only 2025 postseason total probabilities: '+json.dumps(naive,sort_keys=True)]
    (OUT/'README.md').write_text('\n'.join(table)+'\n')
    print('FINAL_LCS_METRICS',json.dumps(report['all_games'],sort_keys=True),flush=True)
    print('FULL_POSTSEASON_RESEARCH_ARTIFACTS',str(OUT),flush=True)


if __name__=='__main__':
    replay()
