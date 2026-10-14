"""Lightweight GitHub Actions verifier: ensure scheduled eligible games were saved.

Independent of the model dependencies; executes on a fresh checkout after
forecast execution. Prevents silent 'green' runs that produced no game record.
The deployment may still succeed; this check is a separate job.
"""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path

def parse_expected(csv_ids):
    ids=set()
    for token in str(csv_ids or '').split(','):
        token=token.strip()
        if not token:continue
        if not token.isdigit():raise ValueError('Expected game ID must contain digits only')
        ids.add(token)
    return sorted(ids)

def _date(s):
    value=datetime.fromisoformat(str(s).replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('Missing timezone in original')
    return value

def check(root,expected):
    root=Path(root)
    originals=root/'cloud_records/predictions'
    present=[]
    missing=[]
    invalid=[]
    for game_id in sorted(expected):
        path=originals/(game_id+'.json')
        if not path.exists():
            missing.append(game_id)
            continue
        try:
            r=json.loads(path.read_text(encoding='utf-8'))
            a=_date(r['forecast_created_utc']);b=_date(r['game_start_utc'])
            if (str(r['game_id'])!=game_id or r.get('forecast_kind')=='revised_pregame'
                or not a<b or not r.get('date') or r.get('away')==r.get('home')):
                invalid.append(game_id)
            else:present.append(game_id)
        except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
            invalid.append(game_id)
    events=[]
    last=root/'cloud_records/last_run.json'
    try:
        last_data=json.loads(last.read_text(encoding='utf-8'))
        for e in last_data.get('events',[]):
            if isinstance(e,dict) and e.get('status')=='forecast_failed':
                events.append(e)
    except (OSError,TypeError,ValueError):
        last_data={}
    report={'expected_game_ids':sorted(expected),'confirmed_original_game_ids':present,
            'missing_game_ids':missing,'invalid_game_ids':invalid,
            'last_run_started_utc':last_data.get('run_started_utc'),
            'last_run_status':last_data.get('status','unknown'),
            'forecast_errors_in_last_run':events,
            'passed':not missing and not invalid and not events}
    return report

def as_markdown(report):
    s=['## MLB Forecast Lab — Scheduled Forecast Health','',
       f"Expected scheduled games: **{len(report['expected_game_ids'])}**",
       f"Valid saved original forecasts: **{len(report['confirmed_original_game_ids'])}**",
       f"Missing originals: **{len(report['missing_game_ids'])}**",
       f"Invalid originals: **{len(report['invalid_game_ids'])}**",
       f"Forecast errors recorded in last run: **{len(report['forecast_errors_in_last_run'])}**",
       f"Model run: \`{report['last_run_status']}\` · {report['last_run_started_utc'] or 'unknown'}",'']
    if report['missing_game_ids']:s+=['Missing game IDs: '+', '.join(report['missing_game_ids'])]
    if report['invalid_game_ids']:s+=['Invalid game IDs: '+', '.join(report['invalid_game_ids'])]
    s+=['','This is an execution-integrity check, **not** a claim that a baseball forecast was correct.',
        'A missed GitHub start window cannot be repaired by fabricating a post-first-pitch prediction.']
    return '\n'.join(s)+'\n'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--expected-game-ids',default=os.getenv('EXPECTED_GAME_IDS',''))
    p.add_argument('--summary-file',type=Path)
    args=p.parse_args()
    result=check(args.root,parse_expected(args.expected_game_ids))
    print(json.dumps(result,indent=2))
    location=args.summary_file or (Path(os.environ['GITHUB_STEP_SUMMARY']) if os.environ.get('GITHUB_STEP_SUMMARY') else None)
    if location:
        with location.open('a',encoding='utf-8') as f:f.write(as_markdown(result))
    if not result['passed']:
        print('::error::Forecast health monitor detected missing/invalid original or a recorded forecast error')
        raise SystemExit(1)
if __name__=='__main__':main()
