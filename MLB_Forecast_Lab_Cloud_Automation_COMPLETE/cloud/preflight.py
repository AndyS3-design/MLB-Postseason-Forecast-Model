"""Cheap (stdlib-only) MLB pregame gate for GitHub Actions.

The expensive forecasting job runs only when a first pitch is getting close,
when explicitly requested, or during the daily maintenance run. Cron timing is
best-effort; the forecasting worker independently checks the actual cutoff.
"""
from __future__ import annotations
import argparse,json,os,sys
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from pathlib import Path
from zoneinfo import ZoneInfo
# Both `python cloud/preflight.py` (GitHub gate) and module imports must work.
if __package__:
    from cloud.two_stage import eligible_preliminary, EARLIEST_PREVIEW_HOUR_ET
    from cloud.model_version import VERSION
else:
    from two_stage import eligible_preliminary, EARLIEST_PREVIEW_HOUR_ET
    from model_version import VERSION

APP_ROOT=Path(__file__).resolve().parents[1]
# The official ID mapping lives in a stdlib-only importer. The direct-script
# gate starts with cloud/ on sys.path, unlike the worker's module invocation.
if not __package__:
    sys.path.insert(0, str(APP_ROOT))
from ingest_mlb import MLB_TO_RETRO
EASTERN=ZoneInfo('America/New_York')

API='https://statsapi.mlb.com/api/v1/schedule'
# GitHub cron may be delayed or dropped for hours. Reserve a job up to four
# hours early, then wait in cloud.pregame_wait until the safe final window.
# The WORKER still independently enforces the strict 8–30-minute cutoff.
# This is a scheduling envelope, not permission to backdate a forecast.
MIN_LEAD_MINUTES=10
MAX_LEAD_MINUTES=39
EARLY_RESERVATION_MAX_LEAD_MINUTES=240
GAME_TYPES={'R','F','D','L','W'}
ALLOWED_STATES={'preview','pre-game','pregame','scheduled','warmup'}

def official_schedule_days(now):
    """MLB indexes games by official US date, including after UTC midnight."""
    if now.tzinfo is None:
        raise ValueError('Schedule gate requires an aware current time')
    today=now.astimezone(EASTERN).date()
    return (today,today-timedelta(days=1),today+timedelta(days=1))


def _schedule_games(now,fetcher):
    errors=[]
    days=official_schedule_days(now)
    for day in days:
        try:
            payload=fetcher(day)
        except Exception as exc:
            errors.append(exc)
            continue
        for block in payload.get('dates',[]):
            for game in block.get('games',[]):
                yield block,game
    # A failed adjacent-day lookup must not suppress a verified current game.
    if len(errors)==len(days):
        raise errors[0]


def find_approaching_games(now,fetcher=None,max_lead_minutes=MAX_LEAD_MINUTES):
    if fetcher is None:fetcher=fetch_schedule
    matches=[]
    seen_ids=set()
    for block,game in _schedule_games(now,fetcher):
        if game.get('gameType') not in GAME_TYPES:continue
        state=str(game.get('status',{}).get('detailedState','')).strip().lower()
        if state not in ALLOWED_STATES:continue
        try:
            start=datetime.fromisoformat(game['gameDate'].replace('Z','+00:00'))
            if start.tzinfo is None:continue
            lead=(start-now).total_seconds()/60
        except (ValueError,KeyError,TypeError):continue
        game_id=str(game.get('gamePk') or '')
        if MIN_LEAD_MINUTES<=lead<=max_lead_minutes and game_id.isdigit() and game_id not in seen_ids:
            seen_ids.add(game_id)
            matches.append({'id':game_id,
                            'starts_utc':start.isoformat(),
                            'lead_minutes':round(lead,1)})
    return matches

def find_preliminary_games(now, root=APP_ROOT, fetcher=None):
    """Only wake the model for missing, safely early day-of previews."""
    if now.astimezone(EASTERN).hour < EARLIEST_PREVIEW_HOUR_ET:
        return []
    if fetcher is None:
        fetcher = fetch_schedule
    local_day = now.astimezone(EASTERN).date()
    payload = fetcher(local_day)
    output = []
    seen = set()
    for block in payload.get('dates', []):
        for g in block.get('games', []):
            game_id = str(g.get('gamePk') or '')
            if game_id in seen:
                continue
            seen.add(game_id)
            if (Path(root, 'cloud_records', 'preliminary', game_id + '.json').exists()
                    or Path(root, 'cloud_records', 'predictions', game_id + '.json').exists()):
                continue
            game_day = g.get('officialDate') or block.get('date')
            if eligible_preliminary(game_id, game_day, g.get('gameDate'),
                                    g.get('gameType'), g.get('status', {}).get('detailedState'),
                                    now):
                output.append({'id': game_id, 'starts_utc': g['gameDate'],
                               'preview': True})
    return output


def _record(path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError,TypeError):
        return {}


def find_pending_request_games(now,root=APP_ROOT,fetcher=None):
    """Retry authorized, unfulfilled requests while the worker can accept them.

    This only wakes the worker. It still verifies official orders, timing and
    authorization at computation and save time, and owns all immutable writes.
    """
    state=Path(root)/'cloud_records'
    request_types=(
        ('revision_requests','one_time_pregame_revision','revisions'),
        ('preliminary_update_requests','one_time_preliminary_update','preliminary_revisions'),
        ('lineup_refresh_requests','one_time_confirmed_lineup_refresh','lineup_previews'),
    )
    if not any(any((state/directory).glob('*.json'))
               for directory,_,_ in request_types):
        return []
    if fetcher is None:fetcher=fetch_schedule
    output=[]
    seen=set()
    for block,game in _schedule_games(now,fetcher):
        game_id=str(game.get('gamePk') or '')
        if not game_id.isdigit() or game_id in seen:continue
        seen.add(game_id)
        game_day=game.get('officialDate') or block.get('date')
        if (game.get('gameType') not in GAME_TYPES or
                str(game.get('status',{}).get('detailedState','')).strip().lower() not in ALLOWED_STATES):
            continue
        try:
            start=datetime.fromisoformat(game['gameDate'].replace('Z','+00:00'))
            if start.tzinfo is None:continue
            lead=(start-now).total_seconds()/60
            teams=game['teams']
            home=MLB_TO_RETRO[int(teams['home']['team']['id'])]
            away=MLB_TO_RETRO[int(teams['away']['team']['id'])]
            if home==away:continue
        except (ValueError,TypeError,KeyError):
            continue
        original_path=state/'predictions'/f'{game_id}.json'
        for directory,kind,target_directory in request_types:
            request=_record(state/directory/f'{game_id}.json')
            if (request.get('game_id')!=game_id or request.get('date')!=game_day or
                    request.get('kind')!=kind or
                    any((state/target_directory).glob(f'{game_id}_*.json'))):
                continue
            revision=directory=='revision_requests'
            if not revision and original_path.exists():continue
            original=_record(original_path if revision else state/'preliminary'/f'{game_id}.json')
            if (not original or str(original.get('game_id'))!=game_id or
                    original.get('date')!=game_day or original.get('home')!=home or
                    original.get('away')!=away):
                continue
            if revision:
                try:
                    first=datetime.fromisoformat(str(original['forecast_created_utc']).replace('Z','+00:00'))
                    if first.tzinfo is None or not first<now or not 12<=lead<=150:continue
                except (KeyError,ValueError,TypeError):
                    continue
            elif not eligible_preliminary(game_id,game_day,game.get('gameDate'),
                    game.get('gameType'),game.get('status',{}).get('detailedState'),now):
                continue
            if (directory=='preliminary_update_requests' and
                    (request.get('required_model_version')!=VERSION or
                     original.get('model_version')==VERSION)):
                continue
            output.append({'id':game_id,'starts_utc':start.isoformat(),
                           'request_kind':kind})
    return output


def fetch_schedule(day):
    q=urlencode({'sportId':1,'date':day.isoformat(),'gameTypes':','.join(sorted(GAME_TYPES))})
    with urlopen(Request(API+'?'+q,headers={'User-Agent':'MLB Forecast Lab scheduling / 1.0'}),timeout=12) as f:
        return json.load(f)

def daily_maintenance_due(root,now):
    """Run maintenance if no VERIFIED full import finished today in Eastern time."""
    path=Path(root)/'cloud_records/daily_maintenance.json'
    try:
        state=json.loads(path.read_text(encoding='utf-8'))
        stamp=datetime.fromisoformat(str(state['successful_refresh_utc']).replace('Z','+00:00'))
        if stamp.tzinfo is None or stamp>now+timedelta(minutes=5):
            return True
        return stamp.astimezone(EASTERN).date()<now.astimezone(EASTERN).date()
    except (OSError,KeyError,ValueError,TypeError,json.JSONDecodeError):
        return True

def should_run(now,manual=False,maintenance=False,fetcher=None,catchup=False,root=APP_ROOT,reserve_window=False):
    if manual:return {'run':True,'reason':'manually triggered','approaching_games':[], 'preliminary_games':[], 'pending_request_games':[]}
    if maintenance:return {'run':True,'reason':'daily maintenance','approaching_games':[], 'preliminary_games':[], 'pending_request_games':[]}
    if catchup:return {'run':True,'reason':'catch-up official results maintenance','approaching_games':[], 'preliminary_games':[], 'pending_request_games':[]}
    source=fetcher or fetch_schedule
    cache={}
    def cached_schedule(day):
        if day not in cache:
            try:cache[day]=source(day)
            except Exception as exc:cache[day]=exc
        value=cache[day]
        if isinstance(value,Exception):raise value
        return value
    try:
        lead_limit=EARLY_RESERVATION_MAX_LEAD_MINUTES if reserve_window else MAX_LEAD_MINUTES
        matches=[match for match in find_approaching_games(now,cached_schedule,max_lead_minutes=lead_limit)
                 if not (Path(root)/'cloud_records'/'predictions'/
                         (match['id']+'.json')).exists()]
    except Exception as exc:
        # Fail closed. The next scheduled gate will retry, no fabricated matchups.
        return {'run':False,'reason':'schedule fetch failed: '+str(exc)[:140],
                'approaching_games':[], 'preliminary_games':[], 'pending_request_games':[]}
    # An early-preview API failure must never suppress a valid FINAL window.
    try:
        preliminary=find_preliminary_games(now,root=root,fetcher=cached_schedule)
    except Exception as exc:
        preliminary=[]
    try:
        pending=find_pending_request_games(now,root=root,fetcher=cached_schedule)
    except Exception:
        pending=[]
    return {'run':bool(matches or preliminary or pending),
            'reason':'pregame window' if matches else 'early preliminary preview' if preliminary else 'authorized pregame request' if pending else 'no approaching games',
            'approaching_games':matches, 'preliminary_games':preliminary,
            'pending_request_games':pending}

def main():
    p=argparse.ArgumentParser();p.add_argument('--github-output',type=Path)
    p.add_argument('--manual',action='store_true');p.add_argument('--maintenance',action='store_true')
    p.add_argument('--recovery',action='store_true')
    args=p.parse_args();now=datetime.now(timezone.utc)
    catchup=(not args.manual and not args.maintenance and not args.recovery and daily_maintenance_due(APP_ROOT,now))
    result=should_run(now,args.manual,args.maintenance,catchup=catchup,reserve_window=True)
    print(json.dumps({'now_utc':now.isoformat(),**result},indent=2))
    if args.github_output:
        with args.github_output.open('a',encoding='utf-8') as f:
            f.write('run_model='+('true' if result['run'] else 'false')+'\n')
            f.write('mode='+('full' if args.manual or args.maintenance or catchup else 'pregame')+'\n')
            f.write('game_ids='+','.join(sorted({x['id'] for x in result['approaching_games'] if str(x['id']).isdigit()}))+'\n')
            f.write('preliminary_game_ids='+','.join(sorted({x['id'] for x in result.get('preliminary_games', [])}))+'\n')

if __name__=='__main__':main()

