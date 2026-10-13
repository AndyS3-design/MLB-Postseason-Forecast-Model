"""End-to-end V4 matchup forecast. Official data wins over scenarios, missing is explicit."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json
from matchup_model import loaded_details,enrich_games
from v4_matchup_core import historical_team_rows,train_frozen_run_model,make_forecast,VERSION
from v4_sources import (load_prior_boxscores,batter_history,lineup_factor,relief_snapshot,
    pitcher_snapshot,scenario_weather)
from v4_park import park_training_factors
from v4_defense import add_fielding_errors
from v4_simulation import play_games,summarize,seed_for
from v62_pitching import read_calibration,apply_to_base
from v63_postseason import context_for_game,with_context_rates


def build_assets(games,root):
    data=Path(root)/'data'
    details,hands,_=loaded_details(data)
    enriched,n=enrich_games(games,details,hands)
    enriched,fielding_n=add_fielding_errors(enriched,data)
    frame=historical_team_rows(enriched,hands)
    fit=train_frozen_run_model(frame)
    parks=park_training_factors(data)
    return {'enriched':enriched,'hands':hands,'details_n':n,'fit':fit,'parks':parks,'fielding_games_matched':fielding_n}


def generate(games,root,day,match,assets=None,n=30000,
    official_snapshot=None,park_enabled=False,park_override=None,
    temperature=None,wind_mph=None,wind_direction='neutral',roof_closed=False,
    postseason_context_enabled=True,include_2026_snapshot=True):
    root=Path(root);data=root/'data';assets=assets or build_assets(games,root)
    home,away=match['home'],match['away']
    home_sp=match.get('home_pitcher_id') or ''
    away_sp=match.get('away_pitcher_id') or ''
    base=make_forecast(games,data,day,home,away,home_sp,away_sp,
        history_cache=(assets['enriched'],assets['hands'],assets['details_n']),fit_cache=assets['fit'])
    prior=load_prior_boxscores(data,day)
    personnel={}
    for side,team,opp_hand in (('home',home,assets['hands'].get(away_sp,match.get('away_pitcher_hand',''))),
                                ('away',away,assets['hands'].get(home_sp,match.get('home_pitcher_hand','')))):
        pid=match.get(side+'_pitcher_id') or ''
        sp=pitcher_snapshot(data,pid,day)
        ids=(official_snapshot or {}).get('bullpen_ids',{}).get(side)
        bull=relief_snapshot(prior,team,day,ids)
        lineup=(official_snapshot or {}).get('confirmed_lineups',{}).get(side) or []
        if not (official_snapshot or {}).get('is_official_lineup',{}).get(side,False):lineup=[]
        batter_data=batter_history(prior,team,[p['id'] for p in lineup],day,opp_hand) if lineup else []
        lineup_factor_data=lineup_factor(lineup,batter_data,opp_hand)
        personnel[side]=dict(starter=sp,bullpen=bull,lineup=lineup,
                             lineup_batters=batter_data,lineup_adjustment=lineup_factor_data)
    w=scenario_weather(temperature,wind_mph,wind_direction,roof_closed)
    park={'factor':1.,'status':'Neutral: park not enabled or not verified'}
    if park_override is not None:
        value=float(park_override)
        if not .8<=value<=1.2:raise ValueError('Park scenario factor must be between 0.80 and 1.20')
        park={'factor':value,'status':'User-specified, UNVALIDATED park scenario'}
    elif park_enabled and home in assets['parks']:
        park={**assets['parks'][home],
            'status':'UNVALIDATED same-home-stadium assumption; disable if venue is different'}
    # Projected relievers only alter the rate if CURRENT roster has been supplied.
    # Existing team-level bullpen metrics already enter the run fit.
    bullpen_context={'home':1.,'away':1.}
    for side in ('home','away'):
        target='away' if side=='home' else 'home'
        observed=personnel[side]['bullpen']
        if observed['n'] and (official_snapshot or {}).get('bullpen_ids',{}).get(side):
            team_expected=float(base[target+'_features'].get('opp_bp_era',4.35))
            bullpen_context[target]=float(max(.93,min(1.07,1+.035*(observed['era']-team_expected))))
    # V6.2: Optional, 2024-selected starter rate correction. Historical 
    # offense/defense/bullpen model predictions stay as the baseline. Each 
    # starter's rate adjustment is normalized against a neutral-starter 
    # counterfactual, avoiding blindly applying the same ERA twice.
    pitch_cal=read_calibration(root/'outputs'/'v62_pitcher_calibration.json')
    pitch_weight=float(pitch_cal['selected_weight']) if pitch_cal else 0.
    revised_home,revised_away,pitcher_audit=apply_to_base(base,assets['fit'],pitch_weight)
    # V6.3: League-wide postseason run context for totals. The snapshot gate
    # must use the selected game's PRE-first-pitch DATE, never current time.
    post_context=context_for_game(day,
        match.get('game_type','R') if postseason_context_enabled else 'R',
        data/'postseason_context_2022_2026.csv',
        include_2026_snapshot=include_2026_snapshot)
    before_post=(revised_home,revised_away)
    revised_home,revised_away=with_context_rates(revised_home,revised_away,post_context)
    post_context={**post_context,
        'run_model_before':{'home':round(before_post[0],3),'away':round(before_post[1],3),
                            'combined':round(sum(before_post),3)},
        'run_model_after':{'home':round(revised_home,3),'away':round(revised_away,3),
                           'combined':round(revised_home+revised_away,3)}}
    # Historical score distribution is estimated from ONE scoring model.
    # No artificial Elo reweighting is performed.
    match_key=str(match.get('id') or f'{day}:{away}@{home}')
    seed=seed_for(match_key,VERSION)
    params=dict(home_mu=revised_home,away_mu=revised_away,n=n,seed=seed,
      home_starter=personnel['home']['starter'],away_starter=personnel['away']['starter'],
      home_bullpen=personnel['home']['bullpen'],away_bullpen=personnel['away']['bullpen'],
      home_manager_hook=float(base['away_features']['opp_manager_hook']),
      away_manager_hook=float(base['home_features']['opp_manager_hook']),
      home_lineup=personnel['home']['lineup_adjustment']['factor']*bullpen_context['home'],
      away_lineup=personnel['away']['lineup_adjustment']['factor']*bullpen_context['away'],
      park_factor=park['factor'],weather_factor=w['factor'],
      postseason=str(match.get('game_type','R'))!='R')
    draws=play_games(**params)
    forecast=summarize(draws)
    gaps=[]
    for side in ('home','away'):
        if personnel[side]['starter']['known']<3:gaps.append(f'{side} starter fewer than three known previous starts')
        if len(personnel[side]['lineup'])!=9:gaps.append(f'{side} batting order not confirmed before first pitch')
        if not (official_snapshot or {}).get('bullpen_ids',{}).get(side):gaps.append(f'{side} active bullpen roster not confirmed')
    if pitch_cal is None:gaps.append('Starter-run correction not yet calibrated: run py v62_calibrate.py')
    elif pitch_weight==0:gaps.append('Starter-run correction weight is 0: 2024 validation found no improvement')
    elif not any(x['starter_applied'] for x in pitcher_audit.values()):
        gaps.append('Starter-run correction inactive: no verified prior-starter sample included')
    result=dict(model_version=VERSION,date=str(day),match=dict(match),
      home=home,away=away,forecast=forecast,
      baseline={'elo_home_win':base['elo_home'],
       'run_model_home_regulation':base['home_mu'],'run_model_away_regulation':base['away_mu']},
      adjustments={'park':park,'weather':w,'relief_rate_multiplier':bullpen_context,
        'postseason_scoring':post_context,
        'starter_total_rate':{'calibration_status':('2024-selected experimental' if pitch_cal else 'not calibrated'),
          'weight':pitch_weight,'audit':pitcher_audit}},
      personnel=personnel,training=base['training'],simulation=draws['config'],
      data_gaps=gaps,provenance={'official_snapshot':bool(official_snapshot),
        'boxscore_games_used':len(prior),
        'cutoff_exclusive':str(day),'model_frozen_training':'2023-24',
        'pitcher_coverage':{s:personnel[s]['starter']['known'] for s in ('home','away')},
        'fielding_games_matched':assets['fielding_games_matched'],
        'explicit_fielding_feature_selected_in_2024':('opp_field_errors15' in assets['fit'].features)},
      warnings=['This is a research forecast, not a validated betting model.',
        'V6.2 starter adjustment is 2024-selected and must be validated on new, untouched games; do NOT assume elite pitchers always mean an under.',
        'V6.3 postseason scoring is a league-level, shrinkage-based scenario, not a calibrated causal estimate; historical inputs are strictly time gated.',
        'Starter + team model was trained and tested; player lineup, bullpen roster, weather and park scenario overlays are not calibrated.',
        '2025 and 2026 results already influenced development, so future prospective tests are required.',
        'The simulation approximates innings, defensive alignment, and extra innings; it is not pitch-by-pitch.'])
    return result
