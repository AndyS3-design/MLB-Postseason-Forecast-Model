"""Observed team batting totals from completed-game, identity-checked caches.

The API schedule export contains final scores, not batting totals. Attach the
cached boxscore to its exact game ID before constructing historical features.
Outcomes remain postgame observations: feature construction still admits only
strictly earlier dates, including for doubleheaders.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import json
import math
from pathlib import Path

from ingest_mlb import MLB_TO_RETRO


BATTING_FIELDS = {
    'ab': 'atBats', 'hits': 'hits', 'walks': 'baseOnBalls',
    'hbp': 'hitByPitch', 'sf': 'sacFlies', '2b': 'doubles',
    '3b': 'triples', 'hr': 'homeRuns',
}


def _count(value):
    if value is None or isinstance(value, bool) or value == '':
        raise ValueError('Missing batting count')
    number = float(value)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError('Invalid batting count')
    return int(number)


def complete_batting(game, side):
    """Return complete, coherent observed totals; unavailable never means zero."""
    try:
        totals = {key: _count(game.get(side + '_' + key)) for key in BATTING_FIELDS}
    except (ValueError, TypeError, OverflowError):
        return None
    if (totals['ab'] <= 0 or totals['hits'] > totals['ab'] or
            totals['2b'] + totals['3b'] + totals['hr'] > totals['hits']):
        return None
    return totals


def _day(value):
    return date.fromisoformat(str(value)[:10])


def _api_id(game):
    identity = str(game.get('game_id') or '')
    raw = identity.removeprefix('api-')
    return raw if raw.isdigit() else ''


def _identity(game):
    return (_day(game['date']), game['home'], game['away'],
            _count(game['home_final']), _count(game['away_final']))


def _validated_boxscore(raw, game, gid):
    if not isinstance(raw, dict):
        raise ValueError('Boxscore is not an object')
    # /boxscore normally has no game/date metadata. Verify it when included by
    # a cache producer, in addition to the exact filename, teams and final runs.
    for key in ('gamePk', 'gameId'):
        if key in raw and str(raw[key]) != gid:
            raise ValueError('Conflicting cached game ID')
    if 'officialDate' in raw and _day(raw['officialDate']) != _day(game['date']):
        raise ValueError('Conflicting cached game date')
    status = raw.get('status') or {}
    if not isinstance(status, dict):
        raise ValueError('Invalid cached status')
    if status.get('abstractGameState') not in (None, 'Final'):
        raise ValueError('Cached game is not complete')
    teams = raw['teams']
    for side in ('home', 'away'):
        team = teams[side]
        if MLB_TO_RETRO[_count(team['team']['id'])] != game[side]:
            raise ValueError('Conflicting cached team identity')
        batting = team['teamStats']['batting']
        if _count(batting['runs']) != _count(game[side + '_final']):
            raise ValueError('Cached batting is not the recorded final score')
    return teams


def add_team_batting(games, data_dir):
    """Preserve input totals; fill absent totals only from a verified exact game.

    ``games`` are completed results from the Retrosheet/API ingestion pipeline.
    No lookup by date or opponent is allowed, so two games of a doubleheader
    cannot share a boxscore. Failures are explicit optional-data gaps.
    """
    identities = {}
    conflicts = set()
    for game in games:
        gid = _api_id(game)
        if not gid:
            continue
        try:
            identity = _identity(game)
        except (ValueError, TypeError, KeyError, OverflowError):
            conflicts.add(gid)
            continue
        if gid in identities and identities[gid] != identity:
            conflicts.add(gid)
        identities[gid] = identity

    result = []
    for game in games:
        observed = game.copy()
        missing = []
        for side in ('home', 'away'):
            if complete_batting(game, side) is not None:
                observed[side + '_batting_status'] = 'observed_input'
            else:
                missing.append(side)
        if not missing:
            result.append(observed)
            continue
        gid = _api_id(game)
        status = 'missing_boxscore' if gid else 'missing_batting_totals'
        if gid in conflicts:
            status = 'conflicting_game_identity'
        elif gid:
            path = Path(data_dir) / 'mlb_boxscores' / (gid + '.json')
            if path.exists():
                try:
                    home, away = _count(game['home_final']), _count(game['away_final'])
                    if home == away:
                        raise ValueError('No completed untied result')
                    raw = json.loads(path.read_text(encoding='utf-8'))
                    teams = _validated_boxscore(raw, game, gid)
                except (OSError, UnicodeError, ValueError, TypeError, KeyError, OverflowError):
                    status = 'invalid_or_conflicting_boxscore'
                else:
                    for side in missing:
                        try:
                            batting = teams[side]['teamStats']['batting']
                            totals = {key: _count(batting[field]) for key, field in BATTING_FIELDS.items()}
                            candidate = {side + '_' + key: value for key, value in totals.items()}
                            if complete_batting(candidate, side) is None:
                                raise ValueError('Incoherent batting totals')
                            # Existing measurements must agree; incomplete data
                            # must never be silently overwritten by a conflict.
                            for key, value in candidate.items():
                                prior = game.get(key)
                                if prior is not None and prior != '' and not (
                                        isinstance(prior, float) and math.isnan(prior)):
                                    if _count(prior) != value:
                                        raise ValueError('Conflicting existing batting total')
                        except (ValueError, TypeError, KeyError, OverflowError):
                            observed[side + '_batting_status'] = 'invalid_or_conflicting_batting_totals'
                        else:
                            observed.update(candidate)
                            observed[side + '_batting_status'] = 'verified_cached_boxscore'
                    missing = []
        for side in missing:
            observed[side + '_batting_status'] = status
        result.append(observed)
    return result, batting_history_report(result)


def batting_history_report(games, cutoff=None):
    statuses = Counter()
    matched = 0
    for game in games:
        if cutoff is not None and _day(game['date']) >= _day(cutoff):
            continue
        matched += any(game.get(side + '_batting_status') == 'verified_cached_boxscore'
                       for side in ('home', 'away'))
        for side in ('home', 'away'):
            status = game.get(side + '_batting_status')
            statuses[status or ('observed_input' if complete_batting(game, side) else
                                'missing_batting_totals')] += 1
    available = sum(statuses[key] for key in ('observed_input', 'verified_cached_boxscore'))
    return {'team_games_available': available,
            'team_games_unavailable': sum(statuses.values()) - available,
            'cached_games_matched': matched, 'status_counts': dict(statuses)}


def recent_batting_coverage(games, day, team, window=15):
    """Mirror the feature window and season reset, with the same date cutoff."""
    target = _day(day)
    recent = sorted((game for game in games
                     if _day(game['date']).year == target.year and
                     _day(game['date']) < target and team in (game['home'], game['away'])),
                    key=lambda game: (_day(game['date']), str(game.get('game_num', ''))))[-window:]
    known = 0
    statuses = Counter()
    for game in recent:
        side = 'home' if game['home'] == team else 'away'
        available = complete_batting(game, side) is not None
        known += available
        statuses[game.get(side + '_batting_status') or
                 ('observed_input' if available else 'missing_batting_totals')] += 1
    return {'team': team, 'prior_team_games': len(recent), 'known_team_games': known,
            'missing_team_games': len(recent) - known, 'window': window,
            'status_counts': dict(statuses), 'cutoff_exclusive': target.isoformat()}
