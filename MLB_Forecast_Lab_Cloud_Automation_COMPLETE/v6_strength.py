"""Pregame-only MLB offense, defense, and pitching descriptive ratings.

All three ratings are indexed to 100 = league average, HIGHER = better.
Offense is recent runs scored; defense prefers *fielding errors* and otherwise
falls back to a clearly identified runs-allowed proxy; pitching uses earned
runs and recorded outs in actual team-level pitching boxscore CSVs.

These are NOT independently calibrated win probabilities or extra model inputs.
No result from the selected day or later is permitted into any index.
"""
from __future__ import annotations
import csv
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
from statistics import mean
from math import isfinite


def _day(x):
    if isinstance(x,datetime):return x.date()
    if isinstance(x,date):return x
    return date.fromisoformat(str(x)[:10])


def pregame_history_only(games,day):
    """Filter strictly earlier games, irrespective of final-score availability."""
    d=_day(day)
    return [g for g in games if _day(g['date'])<d]


def _optional_int(v):
    try:
        if v is None or str(v).strip() in ('','nan','None'):return None
        number=int(float(v))
        return number if number>=0 else None
    except (TypeError,ValueError):return None


def _team_pitching_rows(data_dir,day):
    """Read completed, PRE-DATE team pitching performances from boxscore detail CSV.

    A doubleheader is two games, each yielding two separate team-level rows.
    Never use date-of-game or subsequent pitching details.
    """
    if data_dir is None:return []
    path=Path(data_dir)/'advanced_pitching_details.csv'
    if not path.exists():return []
    d=_day(day).isoformat();rows=[]
    with path.open(newline='',encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            if not r.get('date') or r['date'][:10]>=d:continue
            side=r.get('side')
            if side not in ('home','away'):continue
            team=r.get(side)
            if not team:continue
            a,b,c,e=(_optional_int(r.get(k)) for k in ('sp_outs','bp_outs','sp_er','bp_er'))
            if None in (a,b,c,e) or a+b==0:continue
            rows.append({'date':r['date'][:10],'team':team,'outs':a+b,'er':c+e,
                         'game':r.get('game_id') or r.get('game_num') or ''})
    return rows


def team_indices(games,day,away,home,lookback=30,prior_games=12,data_dir=None):
    """Three descriptive rating pillars. Return None for unavailable pitching.

    League context is also cut off strictly before target day. League ERA is
    estimated from team earned runs / recorded innings of *prior* boxscores.
    Defense errors are a limited proxy, not Outs Above Average or DRS.
    """
    d=_day(day);past=pregame_history_only(games,d)
    past.sort(key=lambda g:(_day(g['date']),str(g.get('game_num',''))))
    recent=past[-750:]
    league_runs=[float(g[t+'_final']) for g in recent for t in ('home','away')]
    league_rpg=mean(league_runs) if league_runs else 4.5
    if not isfinite(league_rpg) or league_rpg<=0:raise ValueError('Invalid league historical runs')

    errors=[]
    for g in recent:
        for side in ('home','away'):
            num=_optional_int(g.get(side+'_errors'))
            if num is not None:errors.append(num)
    league_err=mean(errors) if len(errors)>=30 else None

    pitching_rows=_team_pitching_rows(data_dir,d)
    league_pitching=sorted(pitching_rows,key=lambda r:(r['date'],r['game']))[-1500:]  # pregame only
    outs_total=sum(x['outs'] for x in league_pitching)
    league_era=27*sum(x['er'] for x in league_pitching)/outs_total if outs_total else None
    pitching_by_team=defaultdict(list)
    for r in pitching_rows:pitching_by_team[r['team']].append(r)

    out={}
    for code in (away,home):
        scores=[];allowed=[];field_errors=[]
        for g in reversed(past):
            if g['home']==code:side='home';other='away'
            elif g['away']==code:side='away';other='home'
            else:continue
            scores.append(float(g[side+'_final']));allowed.append(float(g[other+'_final']))
            error_value=_optional_int(g.get(side+'_errors'))
            if error_value is not None:field_errors.append(error_value)
            if len(scores)>=lookback:break
        if len(scores)<8:
            out[code]={'available':False,'games':len(scores),'offense':None,'defense':None,
                       'pitching':None,'attack':None,'fielding_games':len(field_errors),
                       'pitching_games':0,'defense_source':'unavailable',
                       'pitching_source':'unavailable'}
            continue
        scored=(sum(scores)+prior_games*league_rpg)/(len(scores)+prior_games)
        offense=int(round(max(50,min(155,100*scored/league_rpg))))
        # Prefer genuine errors; only when missing, use run prevention fallback.
        if league_err is not None and len(field_errors)>=8:
            error_rate=(sum(field_errors)+prior_games*league_err)/(len(field_errors)+prior_games)
            # Higher means fewer errors. Factor 0.15 prevents unstable ratios at tiny rates.
            defense=int(round(max(60,min(150,100*(league_err+.15)/(error_rate+.15)))))
            defense_source='Fielding-error proxy (not OAA/DRS)'
        else:
            conceded=(sum(allowed)+prior_games*league_rpg)/(len(allowed)+prior_games)
            defense=int(round(max(50,min(155,100*league_rpg/max(conceded,.01)))))
            defense_source='Runs allowed proxy (INCLUDES pitching; fielding unavailable)'

        last=sorted(pitching_by_team.get(code,[]),key=lambda r:(r['date'],r['game']))[-lookback:]
        team_outs=sum(r['outs'] for r in last)
        if len(last)>=8 and team_outs>0 and league_era is not None and league_era>0:
            # 12 games of league prior prevents inflated performance for tiny samples.
            smooth=(27*sum(r['er'] for r in last)+prior_games*27*league_era)/(team_outs+prior_games*27)
            pitching=int(round(max(55,min(155,100*league_era/max(smooth,.1)))))
            pitching_source='Team pitching ERA (starter + bullpen), smoothed'
        else:
            pitching=None;pitching_source='Detailed pregame pitching records unavailable'
        out[code]={'available':True,'games':len(scores),'offense':offense,
                   'defense':defense,'pitching':pitching,'attack':offense,
                   'fielding_games':len(field_errors),'pitching_games':len(last),
                   'defense_source':defense_source,'pitching_source':pitching_source,
                   'runs_scored_per_game':round(mean(scores),2),
                   'runs_allowed_per_game':round(mean(allowed),2)}
    return {'league_runs_per_team':round(league_rpg,3),'league_pitching_era':round(league_era,3) if league_era is not None else None,
            'teams':out,'cutoff_exclusive':d.isoformat(),
            'note':'Display-only indices; 100 = historical league average, higher is better. Offense from runs scored, defense from errors or labeled fallback, pitching from team-earned runs. NOT win probabilities or direct model inputs.'}
