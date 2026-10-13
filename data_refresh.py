"""Safe 2026 MLB data refresh used by the local dashboard.

For the newest cached month, force a fresh MLB API read. On any failure,
restore earlier cached JSON and CSV files instead of overwriting good data.
No background process or scheduler is installed: auto refresh runs only
when a user opens the dashboard once per local calendar day.
"""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
import json
import subprocess
import sys


def refresh(root: Path, exclusive_day: date, force_latest_month=True, timeout=240):
    root=Path(root); data=root/'data'; raw=data/'mlb_api_json'
    if not 2026<=exclusive_day.year<=2026:
        raise ValueError('The existing importer supports 2026 refreshes only')
    # Refresh the most recent calendar month containing completed dates.
    completed_day=exclusive_day-timedelta(days=1)
    backups={}
    if force_latest_month:
        for path in raw.glob(f'mlb_2026_*_{completed_day.year}-{completed_day.month:02d}-*.json'):
            backups[path]=path.read_bytes()
    outfiles=[data/'mlb_2026_regular.csv',data/'mlb_postseason_2023_2026.csv']
    for path in outfiles:
        backups[path]=path.read_bytes() if path.exists() else None

    def restore():
        for path,content in backups.items():
            if content is None:path.unlink(missing_ok=True)
            else:path.write_bytes(content)

    try:
        for p in backups:
            if p.suffix=='.json':p.unlink(missing_ok=True)
        done=subprocess.run([sys.executable,'ingest_mlb.py','--as-of',exclusive_day.isoformat()],
             cwd=root,text=True,capture_output=True,timeout=timeout,check=False)
        if done.returncode!=0:
            raise RuntimeError((done.stderr or done.stdout or 'Importer failed')[-2800:])
        # Exit code alone is insufficient: the importer exits 0 on unavailable data.
        try:
            result=json.loads(done.stdout)
            if '2026_regular_games' not in result or 'postseason_games' not in result:
                raise ValueError('Missing import counts')
        except (ValueError,TypeError) as exc:
            raise RuntimeError('Importer returned no confirmed 2026 game counts. '+done.stdout[-500:]) from exc
        marker=data/'.dashboard_last_refresh.json'
        marker.write_text(json.dumps({'as_of_exclusive':exclusive_day.isoformat(),
                                     'regular_games':result['2026_regular_games'],
                                     'postseason_records':result['postseason_games']},indent=2))
        return {'ok':True,'result':result,'warnings':done.stderr[-1800:]}
    except Exception:
        restore()
        raise


def refreshed_today(root: Path, today: date):
    marker=Path(root)/'data'/'.dashboard_last_refresh.json'
    try:
        return json.loads(marker.read_text()).get('as_of_exclusive')==today.isoformat()
    except (OSError,ValueError):
        return False
