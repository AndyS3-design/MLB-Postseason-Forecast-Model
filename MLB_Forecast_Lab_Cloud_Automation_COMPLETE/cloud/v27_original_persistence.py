"""Append-only persistence for immutable pregame forecasts.

Normal settlement appends official_final/evaluation to an existing forecast.
Only that transition is permitted; all prediction fields and earlier
settlements are immutable. GitHub Contents writes use the remote blob SHA.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

SETTLEMENT_KEYS = frozenset(('official_final', 'evaluation'))


class ImmutableOriginalError(ValueError):
    """An original forecast's pregame fields or saved settlement changed."""


def _stamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (TypeError, ValueError) as exc:
        raise ImmutableOriginalError('Missing or invalid UTC timestamp') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ImmutableOriginalError('Timestamp must be timezone aware')
    return result.astimezone(timezone.utc)


def _core(obj):
    if not isinstance(obj, dict):
        raise ImmutableOriginalError('Forecast must be a JSON object')
    return {key: value for key, value in obj.items() if key not in SETTLEMENT_KEYS}


def _final_pair(obj):
    final = obj.get('official_final')
    if not isinstance(final, dict):
        raise ImmutableOriginalError('Official settlement must be an object')
    for side in ('home', 'away'):
        score = final.get(side)
        if isinstance(score, bool) or not isinstance(score, int) or score < 0:
            raise ImmutableOriginalError('Official settlement scores must be nonnegative integers')
    if final['home'] == final['away']:
        raise ImmutableOriginalError('MLB final scores cannot tie')
    return final['home'], final['away']


def validate_new_original(record, filename):
    _core(record)
    if str(record.get('game_id')) != filename.removesuffix('.json'):
        raise ImmutableOriginalError('Original game ID does not match filename')
    if record.get('forecast_kind') not in (None, 'original_pregame'):
        raise ImmutableOriginalError('Only original pregame records can be saved here')
    if _stamp(record.get('forecast_created_utc')) >= _stamp(record.get('game_start_utc')):
        raise ImmutableOriginalError('Cannot save a post-first-pitch original')
    if not record.get('date') or not record.get('home') or not record.get('away') or record['home'] == record['away']:
        raise ImmutableOriginalError('Incomplete original identity')
    if 'official_final' in record or 'evaluation' in record:
        raise ImmutableOriginalError('New original cannot already contain a settlement')


def validate_settlement(record):
    _final_pair(record)
    final = record['official_final']
    if final.get('source') != 'Official MLB schedule API':
        raise ImmutableOriginalError('Settlement must identify the official MLB source')
    if _stamp(final.get('settled_at_utc')) < _stamp(record.get('game_start_utc')):
        raise ImmutableOriginalError('Settlement timestamp precedes first pitch')
    if not isinstance(record.get('evaluation'), dict) or not record['evaluation']:
        raise ImmutableOriginalError('Settlement requires its evaluation')


def classify_change(old, new):
    """The core must match; only first final+evaluation append is permitted."""
    if _core(old) != _core(new):
        raise ImmutableOriginalError('Immutable original forecast fields changed')
    old_final = old.get('official_final')
    new_final = new.get('official_final')
    if old_final is not None:
        if old_final != new_final or old.get('evaluation') != new.get('evaluation'):
            raise ImmutableOriginalError('Existing official settlement modified or removed')
        return 'unchanged'
    if 'evaluation' in old:
        raise ImmutableOriginalError('Existing evaluation without official final')
    if new_final is None:
        if old.get('evaluation') != new.get('evaluation'):
            raise ImmutableOriginalError('Evaluation changed without official final')
        return 'unchanged'
    validate_settlement(new)
    return 'settlement_added'


def remote_compatible(local, remote):
    """Concurrent settlement may have a different timestamp; first wins."""
    if _core(local) != _core(remote):
        raise ImmutableOriginalError('Remote original differs in immutable fields')
    if 'official_final' not in remote:
        if 'evaluation' in remote:
            raise ImmutableOriginalError('Remote evaluation has no final')
        return 'needs_settlement' if 'official_final' in local else 'identical'
    validate_settlement(remote)
    if 'official_final' in local:
        validate_settlement(local)
        if (_final_pair(remote) != _final_pair(local) or
                remote['official_final'].get('source') != local['official_final'].get('source') or
                remote.get('evaluation') != local.get('evaluation')):
            raise ImmutableOriginalError('Conflicting settled score or evaluation')
    return 'already_persisted'


def _head_content(path):
    proc = subprocess.run(['git', 'show', 'HEAD:' + path], capture_output=True)
    if proc.returncode:
        check = subprocess.run(['git', 'cat-file', '-e', 'HEAD:' + path], capture_output=True)
        if check.returncode:
            return None
        raise RuntimeError('Cannot read existing original in HEAD: ' + path)
    return json.loads(proc.stdout)


class GithubContents:
    def __init__(self, repo, branch='master'):
        self.repo, self.branch = repo, branch

    def _endpoint(self, path):
        return 'repos/' + self.repo + '/contents/' + path

    def get(self, path):
        proc = subprocess.run(['gh', 'api', self._endpoint(path), '-f', 'ref=' + self.branch,
                               '-X', 'GET'], capture_output=True, text=True)
        if proc.returncode:
            if 'HTTP 404' in proc.stderr:
                return None
            raise RuntimeError('GitHub read failed: ' + proc.stderr[-350:])
        item = json.loads(proc.stdout)
        if item.get('encoding') != 'base64' or not item.get('sha'):
            raise RuntimeError('Unexpected GitHub Contents response')
        return json.loads(base64.b64decode(item['content'])), item['sha']

    def put(self, path, record, sha=None):
        body = {'message': 'Append official settlement without altering original forecast' if sha
                else 'Preserve original pregame forecast',
                'content': base64.b64encode((json.dumps(record, indent=2, sort_keys=True,
                           allow_nan=False) + '\n').encode('utf-8')).decode('ascii'),
                'branch': self.branch}
        if sha is not None:
            body['sha'] = sha
        proc = subprocess.run(['gh', 'api', '--method', 'PUT', self._endpoint(path),
                               '--input', '-'], input=json.dumps(body),
                              capture_output=True, text=True)
        if proc.returncode:
            if 'HTTP 409' in proc.stderr or 'HTTP 422' in proc.stderr:
                return False
            raise RuntimeError('GitHub write failed: ' + proc.stderr[-350:])
        return True


def sync(root, transport, head_reader=_head_content):
    """Fail closed on conflict; never clean local data before remote is verified."""
    root = Path(root)
    folder = root / 'MLB_Forecast_Lab_Cloud_Automation_COMPLETE' / 'cloud_records' / 'predictions'
    report = {'checked': 0, 'unchanged': 0, 'created': 0,
              'settlements_appended': 0, 'already_persisted': 0}
    for file in sorted(folder.glob('*.json')):
        rel = file.relative_to(root).as_posix()
        local = json.loads(file.read_text(encoding='utf-8'))
        old = head_reader(rel)
        kind = 'new' if old is None else classify_change(old, local)
        if old is None:
            validate_new_original(local, file.name)
        report['checked'] += 1
        for _ in range(4):
            found = transport.get(rel)
            if found is not None:
                remote, sha = found
                if old is not None and _core(old) != _core(remote):
                    raise ImmutableOriginalError('HEAD and remote original disagree')
                decision = remote_compatible(local, remote)
                if decision != 'needs_settlement':
                    report['unchanged' if kind == 'unchanged' and decision == 'identical'
                           else 'already_persisted'] += 1
                    break
                if kind != 'settlement_added':
                    raise ImmutableOriginalError('Cannot add settlement without validated local append')
                if transport.put(rel, local, sha=sha):
                    report['settlements_appended'] += 1
                    break
            else:
                if old is not None:
                    raise ImmutableOriginalError('Previously committed original disappeared remotely')
                if transport.put(rel, local):
                    report['created'] += 1
                    break
        else:
            raise RuntimeError('Unable to verify forecast after 4 retries: ' + rel)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--branch', default='master')
    args = parser.parse_args()
    result = sync(args.root, GithubContents(args.repo, args.branch))
    print('V27_IMMUTABLE_PERSISTENCE', json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
