"""Five completed 2026 LCS games: retrospective V20 winner, totals and true joint odds.

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
import v4_workflow

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'/'research_v20_lcs_five_game'
# Only game identity, schedule date, and team identity, which were knowable
# before first pitch. Absolutely no actual final score, lineup, starting
# pitcher, or in-game status is supplied to the forecasting function.
GAMES=(
 ('2026-10-11','NLCS','849809','LAN','MIL','Los Angeles Dodgers','Milwaukee Brewers'),
 ('2026-10-12','NLCS','849812','LAN','MIL','Los Angeles Dodgers','Milwaukee Brewers'),
 ('2026-10-12','ALCS','849820','CLE','TBA','Cleveland Guardians','Tampa Bay Rays'),
 ('2026-10-13','ALCS','849813','CLE','TBA','Cleveland Guardians','Tampa Bay Rays'),
 ('2026-10-14','NLCS','849811','MIL','LAN','Milwaukee Brewers','Los Angeles Dodgers'),
)
IDS={g[2] for g in GAMES}
LINES=(4.5,5.5)
N=12000


def official_lcs_finals():
    query=urlencode({'sportId':1,'startDate':'2026-10-11',
       'endDate':'2026-10-14','gameTypes':'L','hydrate':'linescore'})
    req=Request('https://statsapi.mlb.com/api/v1/schedule?'+query,
       headers={'User-Agent':'MLB Forecast Lab strict retrospective research/1.0'})
    with urlopen(req,timeout=45) as response:
        data=json.load(response)
    if not isinstance(data.get('dates'),list):
        raise ValueError('MLB returned no verifiable schedule dates')
    results={}
    for day in data['dates']:
        for game in day.get('games',[]):
            gid=str(game.get('gamePk') or '')
            if gid not in IDS:continue
            if game.get('gameType')!='L':
                raise ValueError('Unexpected non-LCS game type '+gid)
            status=(game.get('status') or {})
            if status.get('abstractGameState')!='Final':
                raise ValueError('A target game is not officially Final: '+gid)
            pair=game.get('teams') or {}
            try:
                h=int(pair['home']['score']);a=int(pair['away']['score'])
            except (KeyError,TypeError,ValueError):
                line=(game.get('linescore') or {}).get('teams') or {}
                h=int(line['home']['runs']);a=int(line['away']['runs'])
            if min(h,a)<0 or h==a:
                raise ValueError('Invalid official MLB final score for '+gid)
            final={'game_id':gid,'official_date':game.get('officialDate') or day.get('date'),
                   'home_final':h,'away_final':a,
                   'source':'Official MLB Stats API Final schedule endpoint'}
            if gid in results and results[gid]!=final:raise ValueError('Contradictory MLB finals '+gid)
            results[gid]=final
    if set(results)!=IDS:
        raise ValueError('Expected exactly five final LCS games, got '+repr(sorted(results)))
    for day,series,gid,*_ in GAMES:
        if results[gid]['official_date']!=day:
            raise ValueError('Official date disagrees with pregame identity for '+gid)
    return results


def replay():
    root=ROOT
    history=all_games(root/'data',True)
    assets=build_assets(history,root)
    if assets['training_years']!=list(range(2016,2026)):
        raise ValueError('Unexpected training years: '+repr(assets['training_years']))
    prior_cache={}
    rows=[]
    for index,(day,series,gid,away,home,away_name,home_name) in enumerate(GAMES,1):
        if day not in prior_cache:
            prior=pregame_history_only(history,day)
            if any(str(x['date'])[:10]>=day for x in prior):
                raise AssertionError('A same-date or later result leaked into features')
            prior_cache[day]=(prior,historical_cutoff_assets(assets,day))
        prior,filtered_assets=prior_cache[day]
        # Do not assert historical game-start times or lineup identities that
        # aren't archived from a genuine pregame source.
        match=clean_game_input({'id':gid,'date':day,'game_type':'L',
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
        row={'game_id':gid,'series':series,'date':day,
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
    finals=official_lcs_finals()
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
    report={'as_of_utc':datetime.now(timezone.utc).isoformat(),
       'type':'RETROSPECTIVE_FIXED_CURRENT_MODEL_NOT_PROSPECTIVE',
       'model_version':rows[0]['model_version'],
       'sample_size':len(rows),'simulations_per_game':N,
       'scope':'2026 ALCS Rays vs Guardians + NLCS Brewers vs Dodgers, all official finals through October 14',
       'all_games':metric(rows),
       'by_series':{s:metric([x for x in rows if x['series']==s]) for s in ('ALCS','NLCS')},
       'game_rows':rows,
       'limitations':[
         '2026 postseason game outcomes were known during V20 development; this is retrospective and cannot validate an unseen trading edge.',
         'Historical starting pitchers and actual nine-player batting orders are OMITTED because no independent, timestamped pregame source is available for each past game.',
         'Source uses strictly earlier-date historical features and does NOT supply actual final scores until all five probability forecasts are complete.',
         'Kalshi closing odds, fees, fills and exact markets were not provided. No actual trading ROI or profitable edge is established.',
         'Winner+Over joint chances are measured DIRECTLY from shared individual simulations, not by multiplying marginal win and over chances.',
         'Only five completed Championship Series games were available; October 15 games are future fixtures and excluded.']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'lcs_five_game_v20_metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    names=list(rows[0])
    with (OUT/'lcs_five_game_v20_per_game.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:(json.dumps(v,sort_keys=True) if isinstance(v,dict) else v) for k,v in row.items()})
    table=['# Oct 11–14 2026 LCS games: current V20 retrospective replay','',
      '**Research replay only.** No postgame batting orders or pitcher identities were used as pregame predictors. Outcomes are verified independently from official MLB final-score feed *after* every forecast was calculated.','',
      '| Game | Actual away–home | Model winner | Win p | Winner hit | Over 4.5 p | O4.5 hit | Over 5.5 p | O5.5 hit | Pick + O4.5 hit | Pick + O5.5 hit |',
      '|---|---:|---|---:|:---:|---:|:---:|---:|:---:|:---:|:---:|']
    for x in rows:
        table.append(f"| {x['date']} {x['away_abbr']}@{x['home_abbr']} | {x['actual_away_runs']}–{x['actual_home_runs']} | {x['model_winner_pick']} | {x['win_probability']:.1%} | {'Yes' if x['picked_winner_correct'] else 'No'} | {x['p_over_4_5']:.1%} | {'Yes' if x['actual_over_4_5'] else 'No'} | {x['p_over_5_5']:.1%} | {'Yes' if x['actual_over_5_5'] else 'No'} | {'Yes' if x['picked_winner_plus_over_4_5_hit'] else 'No'} | {'Yes' if x['picked_winner_plus_over_5_5_hit'] else 'No'} |")
    a=report['all_games']
    table+=['',f"Winner picks: **{a['winner_correct']}/{a['n']}**. Model over 4.5 direction correct: **{a['over_4_5_correct']}/{a['n']}**; Over 5.5: **{a['over_5_5_correct']}/{a['n']}**.",
        f"Both winner pick + Over 4.5 correct: **{a['picked_winner_and_over_4_5_hits']}/{a['n']}**; winner pick + Over 5.5: **{a['picked_winner_and_over_5_5_hits']}/{a['n']}**.",
        f"Total-run MAE: {a['expected_total_mae']:.3f}; winner Brier: {a['winner_brier']:.4f}; Elo on same five: {a['elo_brier_same_games']:.4f}.",
        '', '## Limitations','']+['- '+x for x in report['limitations']]
    (OUT/'README.md').write_text('\n'.join(table)+'\n')
    print('FINAL_LCS_METRICS',json.dumps(report['all_games'],sort_keys=True),flush=True)
    print('RESEARCH_ARTIFACTS',str(OUT),flush=True)


if __name__=='__main__':
    replay()
