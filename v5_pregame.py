"""V5 conservative MLB confirmed-context parsing for scenario overlays."""
from __future__ import annotations
import re
from datetime import datetime,timezone


def parse_mlb_weather(snapshot):
    """Only use reported temperature/wind direction, not inferred stadium orientation."""
    weather=(snapshot or {}).get('weather') or {}
    try:
        raw=weather.get('temp')
        temp=float(raw) if raw is not None else None
        if temp is not None and not -20<=temp<=125:temp=None
    except (TypeError,ValueError):temp=None
    wind=str(weather.get('wind') or '').lower()
    speed_match=re.search(r'\b(\d+(?:\.\d+)?)\s*mph\b',wind)
    speed=float(speed_match.group(1)) if speed_match else None
    direction='neutral'
    if re.search(r'out\s+to|out\s+toward',wind):direction='out'
    if re.search(r'in\s+from|in\s+toward',wind):direction='in'
    # When MLB says e.g. '9 mph, W', cannot know effect relative to field.
    if speed is None or direction=='neutral':speed=None
    return {'temp':temp,'wind_mph':speed,'direction':direction,
            'raw_weather':weather,'verified':bool(temp is not None or speed is not None),
            'status':'MLB-pregame feed; impact coefficient not historically validated'}


def pregame_start_utc(match):
    try:
        val=datetime.fromisoformat(str(match.get('start_utc','')).replace('Z','+00:00'))
        return val if val.tzinfo is not None else None
    except (TypeError,ValueError):return None


def is_verified_pregame(match,now=None):
    time=pregame_start_utc(match)
    return bool(str(match.get('id','')).isdigit() and time and
                (now or datetime.now(timezone.utc))<time)


def data_readiness(result):
    sides=result.get('personnel',{})
    found=[]
    for side in ('away','home'):
        team=sides.get(side,{})
        found.append({'Side':side.title(),'Starter prior starts':team.get('starter',{}).get('known',0),
            'Official batting order':f"{len(team.get('lineup',[]))}/9",
            'Active bullpen verified':'Yes' if any(x.get('roster_known') for x in team.get('bullpen',{}).get('profiles',[])) else 'No'})
    return found
