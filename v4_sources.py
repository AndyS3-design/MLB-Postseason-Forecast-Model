"""Verified or explicitly labeled optional MLB matchup data inputs.

No retrospective API lookup is accepted as pregame lineup evidence.
Historical boxscores are consumed only for games dated strictly before target.
"""
from __future__ import annotations
import csv,json,math
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
import numpy as np
from import_mlb_boxscores import outs_from_ip

FEED_API='https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live'


def _iso_day(v):return str(v)[:10]


def json_get(url,timeout=20):
    req=Request(url,headers={'User-Agent':'MLB Prediction Lab educational 4.0'})
    with urlopen(req,timeout=timeout) as r:return json.load(r)


def capture_official_pregame(game_id,scheduled_start_utc,now=None,fetcher=None):
    """Only pre-first-pitch verified snapshots. No after-game boxscore lookahead."""
    if not str(game_id).isdigit():raise ValueError('Official MLB numeric gamePk required')
    if not scheduled_start_utc:raise ValueError('Official UTC first pitch required')
    now=now or datetime.now(timezone.utc)
    scheduled=datetime.fromisoformat(str(scheduled_start_utc).replace('Z','+00:00'))
    if now.tzinfo is None:raise ValueError('now must have timezone')
    if now>=scheduled:raise ValueError('Official pregame snapshot blocked after scheduled first pitch')
    raw=(fetcher or json_get)(FEED_API.format(game_id=game_id))
    detailed=str(raw.get('gameData',{}).get('status',{}).get('detailedState',''))
    abstract=str(raw.get('gameData',{}).get('status',{}).get('abstractGameState',''))
    if abstract.lower() in ('live','final') or 'progress' in detailed.lower():
        raise ValueError('Game already started; snapshot cannot be certified pregame')
    box=raw.get('liveData',{}).get('boxscore',{}).get('teams',{})
    meta=raw.get('gameData',{})
    lists={};rosters={}
    for side in ('home','away'):
        team=box.get(side,{})
        players=team.get('players') or {}
        batter_ids=team.get('battingOrder') or []
        lined=[]
        for pid in batter_ids:
            entry=players.get('ID'+str(pid)) or players.get(str(pid)) or {}
            obj=entry.get('person') or {}
            if obj.get('id'):
                hand=((obj.get('batSide') or {}).get('code') or '').upper()
                lined.append(dict(id=int(obj['id']),name=obj.get('fullName') or str(pid),
                                   batting_hand=hand if hand in ('L','R','S') else ''))
        lists[side]=lined
        rosters[side]=[int(pid) for pid in (team.get('bullpen') or []) if str(pid).isdigit()]
    weather=meta.get('weather') or {}
    return dict(game_id=str(game_id),captured_utc=now.isoformat(),
        scheduled_start_utc=scheduled.isoformat(),confirmed_lineups=lists, bullpen_ids=rosters,
        is_official_lineup={s:len(lists[s])==9 for s in ('home','away')},
        weather={'temp':weather.get('temp'),'wind':weather.get('wind'),'condition':weather.get('condition')},
        venue=(meta.get('venue') or {}).get('name','Unavailable'),
        source='MLB Stats API pregame live feed',game_status=detailed)


def _past_games(data_dir,target_date):
    path=Path(data_dir)/'mlb_2026_regular.csv'
    second=Path(data_dir)/'mlb_postseason_2023_2026.csv'
    games={}
    for f in (path,second):
        if not f.exists():continue
        with f.open(encoding='utf-8-sig',newline='') as fh:
            for row in csv.DictReader(fh):
                if row.get('year')!='2026' or row.get('date','')[:10]>=_iso_day(target_date):continue
                gid=row.get('game_id','')
                if str(gid).isdigit():games[str(gid)]=dict(date=_iso_day(row['date']),home=row['home'],away=row['away'])
    return games


def load_prior_boxscores(data_dir,target_date,max_games=2600):
    """Only cached BOX SCORES of previously completed 2026 games. No game-day records."""
    historic=_past_games(data_dir,target_date)
    cache=Path(data_dir)/'mlb_boxscores'
    out=[]
    for gid,metadata in sorted(historic.items(),key=lambda x:x[1]['date'])[-max_games:]:
        f=cache/(gid+'.json')
        if not f.exists():continue
        try:raw=json.loads(f.read_text(encoding='utf-8'))
        except (json.JSONDecodeError,UnicodeDecodeError):continue
        if not (raw.get('teams') or {}).get('home'):continue
        out.append((metadata,raw))
    return out


def _num(v):
    try:return max(0,int(v or 0))
    except (TypeError,ValueError):return 0


def batter_history(prior,side_team:str,player_ids:list[int],day,opp_starter_hand=''):
    """Build prior performance from actual game batting records; no season-to-date API leakage.

    Game-level past opponent-hand is not known here; hand matchup overlay is a labeled
    league-level scenario, NOT a batter-vs-pitcher trained split.
    """
    chosen={int(x) for x in player_ids}
    entries=defaultdict(list)
    for meta,raw in prior:
        day_=_iso_day(meta['date'])
        if day_>=_iso_day(day):continue
        for side in ('home','away'):
            if meta[side]!=side_team:continue
            team=raw.get('teams',{}).get(side,{})
            for pid in chosen:
                rec=(team.get('players') or {}).get('ID'+str(pid)) or {}
                stat=rec.get('stats',{}).get('batting',{})
                if not stat:continue
                ab=_num(stat.get('atBats'));bb=_num(stat.get('baseOnBalls'))
                hbp=_num(stat.get('hitByPitch')); sf=_num(stat.get('sacFlies'))
                if ab+bb+hbp+sf==0:continue
                h=_num(stat.get('hits'));doubles=_num(stat.get('doubles'))
                triples=_num(stat.get('triples'));hr=_num(stat.get('homeRuns'))
                singles=max(0,h-doubles-triples-hr)
                entries[pid].append(dict(date=day_,pa=ab+bb+hbp+sf,
                  weighted=0.69*bb+0.72*hbp+0.89*singles+1.27*doubles+1.62*triples+2.10*hr))
    out=[]
    for pid in player_ids:
        obs=sorted(entries.get(int(pid),[]),key=lambda a:a['date'])[-60:]
        pa=sum(x['pa'] for x in obs);total=sum(x['weighted'] for x in obs)
        # Prior: ~150 PAs of league-scale .320 wOBA.
        est=(total+150*.320)/(pa+150)
        out.append(dict(id=int(pid),observed_pa=pa,estimated_woba=float(est),games=len(obs)))
    return out


def lineup_factor(lineup:list[dict],batter_records:list[dict],opp_starter_hand=""):
    """Exploratory, explicitly uncalibrated and bounded lineup-vs-league correction."""
    if len(lineup)!=9 or len(batter_records)!=9:
        return dict(factor=1.0,status='Unavailable: verified nine-player lineup required',n=0)
    prior_pa=sum(x['observed_pa'] for x in batter_records)
    if prior_pa<400:return dict(factor=1.,status='Unavailable: fewer than 400 observed prior lineup PAs',n=prior_pa)
    avg_woba=float(np.mean([x['estimated_woba'] for x in batter_records]))
    # A tiny generic platoon scenario; NOT an empirically validated hitter/pitcher
    # split and should NOT be mistaken for Statcast matchup data.
    matchup_effect=0.
    if opp_starter_hand in ('L','R'):
        for p in lineup:
            bat=p.get('batting_hand','')
            if bat in ('L','R'):
                matchup_effect+=(-.006 if bat==opp_starter_hand else .004)/9
    # 0.320 neutral. Bound the unvalidated lineup-vs-league sensitivity.
    value=float(np.clip(1+1.2*(avg_woba+.0+matchup_effect-.320),.88,1.12))
    return dict(factor=value,status='EXPERIMENTAL: lineup wOBA + generic handedness proxy; not fitted/calibrated',
       n=prior_pa,mean_woba=avg_woba,handedness_woba_scenario=matchup_effect,
       opposing_starter_hand=opp_starter_hand or 'unknown')


def relief_snapshot(prior,team:str,day,official_bullpen_ids=None):
    """Pitcher-level history & fatigue proxy. Roster eligibility is known ONLY with a verified list."""
    byid=defaultdict(list)
    for meta,raw in prior:
        if _iso_day(meta['date'])>=_iso_day(day):continue
        for side in ('home','away'):
            if meta[side]!=team:continue
            bs=raw.get('teams',{}).get(side,{})
            pitchers=bs.get('pitchers') or []
            for player_id in pitchers[1:]:
                p=(bs.get('players') or {}).get('ID'+str(player_id)) or {}
                s=p.get('stats',{}).get('pitching',{})
                outs=outs_from_ip(s.get('inningsPitched'))
                if outs is None:continue
                byid[int(player_id)].append(dict(date=_iso_day(meta['date']),outs=outs,
                    er=_num(s.get('earnedRuns')),pitches=_num(s.get('numberOfPitches')),
                    name=(p.get('person') or {}).get('fullName') or str(player_id)))
    verified_set={int(x) for x in (official_bullpen_ids or [])}
    day_d=date.fromisoformat(_iso_day(day))
    profiles=[]
    for pid,all_rows in byid.items():
        history=sorted(all_rows,key=lambda x:x['date'])[-30:]
        if not history:continue
        last=(day_d-date.fromisoformat(history[-1]['date'])).days
        if last>45:continue
        pitches3=sum(x['pitches'] for x in history if (day_d-date.fromisoformat(x['date'])).days<=3)
        outs=sum(x['outs'] for x in history);er=sum(x['er'] for x in history)
        smooth=(er*27+27*4.35)/(outs+27) # 9-IP starter prior
        profiles.append(dict(id=pid,name=history[-1]['name'],observed_ip=round(outs/3,1),
          smoothed_era=round(smooth,2),pitches_last_3d=pitches3,
          likely_fatigued=pitches3>=55 or (pitches3>=30 and last<=1),
          roster_confirmed=bool(verified_set) and pid in verified_set,
          roster_known=bool(verified_set),days_since_appearance=last))
    profiles.sort(key=lambda z:(not z['roster_confirmed'] if verified_set else False,z['likely_fatigued'],z['smoothed_era']))
    if verified_set:eligible=[p for p in profiles if p['roster_confirmed']]
    else:eligible=profiles[:10]  # not confirmed active: only a historical research proxy
    ready=[p for p in eligible if not p['likely_fatigued']]
    if len(ready)<2:ready=eligible
    if len(ready)<1:return dict(era=4.35,n=0,profiles=profiles[:12],status='No usable reliever history; neutral ERA')
    era=float(np.mean([p['smoothed_era'] for p in ready[:5]]))
    return dict(era=float(np.clip(era,2.5,6.5)),n=len(ready),profiles=profiles[:12],
      status=('Official bullpen ID filtered; still a workload proxy' if verified_set
       else 'Historical pitchers only; current roster/availability NOT verified'))


def pitcher_snapshot(data_dir,pitcher_id,day):
    path=Path(data_dir)/'advanced_pitching_details.csv'
    if not pitcher_id or not path.exists():return dict(era=4.35,innings=5.,known=0,status='No verified prior starts')
    rows=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if (r.get('pitcher_id')==pitcher_id and r.get('date','')[:10]<_iso_day(day)
                and r.get('sp_outs') not in ('',None) and r.get('sp_er') not in ('',None)):
                rows.append(r)
    rows.sort(key=lambda x:x.get('date',''))
    last=rows[-8:]
    if not last:return dict(era=4.35,innings=5.,known=0,status='No verified prior starts')
    outs=sum(_num(x.get('sp_outs')) for x in last);er=sum(_num(x.get('sp_er')) for x in last)
    # Use the same 18-out, 4.30 prior as the historical Starter.signals()
    # feature engine. Previously, the dashboard card used a much stronger
    # 54-out prior and showed a different pitcher ERA from the scoring model.
    era=(er*27+18*4.3)/(outs+18)
    innings=float(np.clip(np.mean([_num(x['sp_outs'])/3 for x in last[-4:]]),2.5,7.5))
    return dict(era=round(float(np.clip(era,1.5,8)),3),innings=round(innings,2),known=len(last),
        status='Smoothed recent starts, prior game dates only')


def scenario_weather(temp=None,wind_mph=None,wind_direction='neutral',roof_closed=False):
    """Bounded UNVALIDATED scenario sensitivity, zero adjustment if unknown/roof closed."""
    temp_adj=0.;wind_adj=0.
    if not roof_closed and temp is not None:
        temp_adj=float(np.clip((float(temp)-70)*.0015,-.07,.07))
    if not roof_closed and wind_mph is not None:
        if wind_direction=='out':wind_adj=min(.08,float(wind_mph)*.004)
        elif wind_direction=='in':wind_adj=-min(.08,float(wind_mph)*.004)
    return dict(factor=float(np.clip(1+temp_adj+wind_adj,.85,1.15)),
        status='Unvalidated weather scenario; not a trained effect',roof_closed=bool(roof_closed))
