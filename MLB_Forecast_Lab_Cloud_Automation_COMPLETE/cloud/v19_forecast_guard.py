"""Independent, stdlib-only MLB final-forecast guard.

Does not train, simulate, backdate, or alter any frozen prediction. A separate
offset cron may ask GitHub to dispatch the real existing forecasting workflow
when a confirmed MLB pregame original is still missing. When MLB officially
starts a game without one, reports an auditable missed-window incident.
"""
from __future__ import annotations
import argparse,json
from datetime import datetime,date,timedelta,timezone
from pathlib import Path

from cloud import preflight

UTC=timezone.utc
TRACKING_START=date(2026,10,14)
DISPATCH_MIN_LEAD=12.
DISPATCH_MAX_LEAD=34.
MISS_REPORT_MAX_HOURS=18.
ACTIVE=('scheduled','pre-game','pregame','preview','warmup','warmups')
STARTED=('in progress','live','final','game over','completed early','completed')
GAME_TYPES={'R','F','D','L','W'}


def _aware(s):
    dt=datetime.fromisoformat(str(s).replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('timestamp without time zone')
    return dt.astimezone(UTC)


def original_status(root,game_id,game):
    """Differentiate missing, valid and invalid immutable original evidence."""
    path=Path(root)/'cloud_records'/'predictions'/f'{game_id}.json'
    if not path.exists():return 'missing'
    try:
        rec=json.loads(path.read_text(encoding='utf-8'))
        created=_aware(rec['forecast_created_utc'])
        scheduled=_aware(rec['game_start_utc'])
        if (str(rec['game_id'])!=game_id
                or rec.get('forecast_kind') not in (None,'original_pregame')
                or created>=scheduled
                or rec.get('date')!=game.get('officialDate')
                or scheduled!=_aware(game['gameDate'])
                or rec.get('home')==rec.get('away')):
            return 'invalid'
        return 'valid'
    except (OSError,KeyError,TypeError,ValueError,json.JSONDecodeError):
        return 'invalid'


def evaluate(root,now,fetcher=None):
    """Official dates and actual status. No results are inferred from a clock."""
    if now.tzinfo is None:raise ValueError('UTC-aware now required')
    now=now.astimezone(UTC)
    fetcher=fetcher or preflight.fetch_schedule
    candidates={}
    for block,game in preflight._schedule_games(now,fetcher):
        gid=str(game.get('gamePk') or '')
        if not gid.isdigit() or game.get('gameType') not in GAME_TYPES:continue
        official=game.get('officialDate') or block.get('date')
        try:
            game_day=date.fromisoformat(str(official))
            start=_aware(game['gameDate'])
        except (TypeError,ValueError,KeyError):
            continue
        if game_day<TRACKING_START:continue
        # MLB returns the same game under several adjacent date queries.
        if gid not in candidates:candidates[gid]=(game,game_day,start)
    report={'checked_utc':now.isoformat(),
            'source':'Official MLB schedule independently of the main preflight gate',
            'status':'no_eligible_games','eligible_games':len(candidates),
            'dispatch_game_ids':[], 'at_risk_game_ids':[],
            'missed_game_ids':[], 'invalid_original_game_ids':[],
            'already_recorded_game_ids':[],'upcoming':[]}
    for gid,(game,game_day,start) in sorted(candidates.items(),key=lambda t:t[1][2]):
        lead=(start-now).total_seconds()/60.
        status=str((game.get('status') or {}).get('detailedState') or '').strip().lower()
        abstract=str((game.get('status') or {}).get('abstractGameState') or '').strip().lower()
        evidence=original_status(root,gid,{**game,'officialDate':game_day.isoformat()})
        if evidence=='valid':
            report['already_recorded_game_ids'].append(gid)
        elif evidence=='invalid':
            report['invalid_original_game_ids'].append(gid)
        if start>=now:
            report['upcoming'].append({'game_id':gid,'official_date':game_day.isoformat(),
                 'scheduled_utc':start.isoformat(),'lead_minutes':round(lead,1),
                 'mlb_state':status,'original':evidence})
        # Trigger only while the WORKER has time to finish in its strict
        # 8–30-minute window; the guard never creates forecasts itself.
        if (evidence=='missing' and status in ACTIVE
                and DISPATCH_MIN_LEAD<=lead<=DISPATCH_MAX_LEAD):
            report['dispatch_game_ids'].append(gid)
        if evidence=='missing' and status in ACTIVE and 0<=lead<DISPATCH_MIN_LEAD:
            report['at_risk_game_ids'].append(gid)
        # Never call a game missed just because scheduled start passed:
        # actual MLB state must indicate play has begun.
        if (evidence=='missing' and status in STARTED
                and 0<=-lead<=MISS_REPORT_MAX_HOURS*60):
            report['missed_game_ids'].append(gid)
        if (evidence=='invalid' and status in STARTED
                and 0<=-lead<=MISS_REPORT_MAX_HOURS*60):
            report['missed_game_ids'].append(gid)
    report['upcoming']=report['upcoming'][:10]
    if report['missed_game_ids']:
        report['status']='missing_original_after_official_start'
    elif report['invalid_original_game_ids']:
        report['status']='invalid_original_record'
    elif report['dispatch_game_ids']:
        report['status']='needs_backup_dispatch'
    elif report['at_risk_game_ids']:
        report['status']='final_forecast_at_risk'
    elif report['eligible_games']:
        report['status']='observed'
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--github-output',type=Path)
    parser.add_argument('--json-file',type=Path)
    args=parser.parse_args()
    report=evaluate(args.root,datetime.now(UTC))
    print(json.dumps(report,indent=2),flush=True)
    if args.json_file:
        args.json_file.parent.mkdir(parents=True,exist_ok=True)
        args.json_file.write_text(json.dumps(report,indent=2)+'\n')
    if args.github_output:
        with args.github_output.open('a',encoding='utf-8') as handle:
            for key in ('dispatch_game_ids','at_risk_game_ids','missed_game_ids',
                        'invalid_original_game_ids'):
                handle.write(key+'='+','.join(report[key])+'\n')
            handle.write('guard_status='+report['status']+'\n')


if __name__=='__main__':main()
