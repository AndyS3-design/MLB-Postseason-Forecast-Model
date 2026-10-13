"""Targeted, past-only MLB starter-history backfill for cloud forecasts.

Why: the maintenance job only imports a small rolling set of full boxscores.
Probable pitchers can therefore have 0-2 local starts even when official
historical starts exist. Retrieve only *verified* games before the forecast's
calendar date, and verify starter identity against official boxscore order.

No odds, markets, live game boxscores, made-up statistics, or after-start data.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from typing import Callable

from import_mlb_boxscores import API, one_game, request_json, write_merged

MAX_MATCHED_BOXSCORES_PER_PITCHER = 16
MAX_PREVIOUS_STARTS = 8
MIN_VERIFIED_STARTS = 3


def _date(value):
    return date.fromisoformat(str(value)[:10])


def _prior_finals(data_dir: Path, cutoff: date) -> dict[str, dict]:
    """Only actual completed game IDs, strictly prior to the date cutoff."""
    paths = sorted(data_dir.glob('mlb_20??_regular.csv'))
    paths.append(data_dir / 'mlb_postseason_2023_2026.csv')
    eligible = {}
    for path in paths:
        if not path.is_file():
            continue
        with path.open(newline='', encoding='utf-8-sig') as file:
            for record in csv.DictReader(file):
                game_id = str(record.get('game_id', ''))
                day = record.get('date', '')
                if not game_id.isdecimal() or not day:
                    continue
                try:
                    if _date(day) >= cutoff:
                        continue
                except ValueError:
                    continue
                if not (record.get('home') and record.get('away')):
                    continue
                if record.get('home_final') in ('', None) or record.get('away_final') in ('', None):
                    continue
                # One official identity per MLB gamePk; fail if data contradicts itself.
                previous = eligible.get(game_id)
                if previous and any(previous.get(k) != record.get(k)
                                    for k in ('date', 'home', 'away')):
                    raise ValueError(f'Conflicting prior MLB game {game_id}')
                eligible[game_id] = record
    return eligible


def _existing_starts(data_dir: Path, pitcher_id: str, cutoff: date):
    path = data_dir / 'advanced_pitching_details.csv'
    if not path.is_file():
        return set()
    starts = set()
    with path.open(newline='', encoding='utf-8-sig') as file:
        for rec in csv.DictReader(file):
            if rec.get('pitcher_id') != pitcher_id:
                continue
            try:
                if _date(rec.get('date', '')) >= cutoff or int(rec.get('sp_outs') or 0) <= 0:
                    continue
            except (ValueError, TypeError):
                continue
            # Retrosheet and MLB IDs differ; each MLB person ID is unambiguous.
            key = rec.get('game_id') or (rec.get('date'), rec.get('home'), rec.get('away'))
            starts.add(str(key))
    return starts


def _cached_complete_boxscore_ids(data_dir: Path, cutoff: date):
    """Avoid downloading games whose two starting pitcher lines are already saved."""
    path = data_dir / 'advanced_pitching_details.csv'
    if not path.is_file():
        return set()
    seen = {}
    with path.open(newline='', encoding='utf-8-sig') as file:
        for row in csv.DictReader(file):
            gid = str(row.get('game_id') or '')
            if not gid.isdecimal() or row.get('side') not in ('home', 'away'):
                continue
            try:
                if _date(row.get('date', '')) >= cutoff:
                    continue
            except ValueError:
                continue
            if row.get('sp_outs') in ('', None) or not row.get('pitcher_id'):
                continue
            seen.setdefault(gid, set()).add(row['side'])
    return {gid for gid, sides in seen.items() if sides == {'home', 'away'}}


def _gamelog_game_ids(pitcher_id: str, season: int, fetcher: Callable) -> list[str]:
    """Official MLB game-log IDs are *candidates*, not proof of starting."""
    person = str(pitcher_id).removeprefix('MLB-')
    if not person.isdecimal():
        return []
    query = urlencode({'stats': 'gameLog', 'group': 'pitching', 'season': season})
    payload = fetcher(f'{API}/people/{person}/stats?{query}')
    ids = []
    for section in payload.get('stats', []):
        for split in section.get('splits', []):
            game = split.get('game') or {}
            game_id = str(game.get('gamePk') or game.get('id') or '')
            if game_id.isdecimal():
                ids.append(game_id)
    return list(dict.fromkeys(ids))


def backfill_match_starters(data_dir, game: dict, cutoff,
                            fetcher: Callable = request_json,
                            boxscore_loader: Callable = one_game,
                            max_boxscores_per_pitcher: int = MAX_MATCHED_BOXSCORES_PER_PITCHER):
    """Fetch prior boxscores *for named starters* and merge only verified data.

    The game's date is an exclusive cutoff. Same-day results never enter the
    model even if they are completed by the time this function runs. The
    `one_game` loader validates actual starter order; identity is checked again.
    """
    data_dir = Path(data_dir)
    cutoff = _date(cutoff)
    if max_boxscores_per_pitcher < 1:
        raise ValueError('max_boxscores_per_pitcher must be positive')
    previous = _prior_finals(data_dir, cutoff)
    cache = data_dir / 'mlb_boxscores'
    cache.mkdir(parents=True, exist_ok=True)
    report = {'status': 'ok', 'cutoff_exclusive': cutoff.isoformat(),
              'source': 'MLB official game logs + completed game boxscores',
              'sides': {}, 'new_boxscores': 0, 'errors': []}
    new_rows = []
    new_people = []
    cached_complete = _cached_complete_boxscore_ids(data_dir, cutoff)
    visited = set()
    for side in ('home', 'away'):
        pid = str(game.get(side + '_pitcher_id') or '')
        before = _existing_starts(data_dir, pid, cutoff) if pid else set()
        added = set()
        diagnostics = {'pitcher_id': pid, 'prior_verified_starts_before': len(before),
                       'prior_verified_starts_after': len(before),
                       'source': 'local history' if before else 'not available',
                       'game_logs_found': 0, 'status': 'unknown'}
        report['sides'][side] = diagnostics
        if not pid.startswith('MLB-') or not pid[4:].isdecimal():
            diagnostics['status'] = 'starter ID not announced or not MLB ID'
            continue
        if len(before) >= MAX_PREVIOUS_STARTS:
            diagnostics['status'] = 'sufficient verified starts already cached'
            continue
        ids = []
        # Current season first. Past seasons require a matching *official*
        # completed-game CSV; never backfill an unknown game without a final.
        seasons = sorted({int(r.get('year') or _date(r['date']).year)
                          for r in previous.values() if _date(r['date']).year <= cutoff.year},
                         reverse=True)
        for season in seasons[:2]:
            if season < cutoff.year - 1:
                continue
            try:
                ids.extend(_gamelog_game_ids(pid, season, fetcher))
            except Exception as exc:
                report['errors'].append(f'{side} MLB game log {season}: {str(exc)[:130]}')
        # A missing/unavailable gameLog should not disable the forecast. Use a
        # bounded scan of the team's most recent verified completed games.
        fallback = [gid for gid, rec in previous.items()
                    if game.get(side) in (rec.get('home'), rec.get('away'))]
        candidate_ids = [gid for gid in set(ids) if gid in previous]
        candidate_ids = sorted(candidate_ids, key=lambda gid: (previous[gid]['date'], int(gid)), reverse=True)
        if len(candidate_ids) < max_boxscores_per_pitcher:
            fallback = sorted(fallback, key=lambda gid: (previous[gid]['date'], int(gid)), reverse=True)
            candidate_ids.extend(gid for gid in fallback if gid not in candidate_ids)
        diagnostics['game_logs_found'] = len(set(ids) & set(previous))
        checks = 0
        for gid in candidate_ids:
            if len(before) + len(added) >= MAX_PREVIOUS_STARTS:
                break
            if checks >= max_boxscores_per_pitcher:
                break
            # Never count the same game twice when a pitcher appears in multiple
            # requests, and never count a relief appearance as a starting job.
            if gid in visited:
                # A previously fetched game may contain the other named starter.
                for r in new_rows:
                    if str(r.get('game_id')) == gid and r.get('pitcher_id') == pid:
                        added.add(gid)
                continue
            if gid in before or gid in cached_complete:
                continue
            checks += 1
            try:
                rows, people = boxscore_loader(previous[gid], cache)
                if len(rows) != 2:
                    raise ValueError('boxscore missing home or away starter')
                if {str(row.get('side')) for row in rows} != {'home', 'away'}:
                    raise ValueError('boxscore sides not verified')
                if any(str(row.get('game_id')) != gid or
                       row.get('date') != previous[gid]['date'] or
                       row.get('home') != previous[gid]['home'] or
                       row.get('away') != previous[gid]['away'] for row in rows):
                    raise ValueError('boxscore identity inconsistent with official final')
                new_rows.extend(rows)
                new_people.extend(people)
                visited.add(gid)
                report['new_boxscores'] += 1
                if any(r.get('pitcher_id') == pid and int(r.get('sp_outs') or 0) > 0 for r in rows):
                    added.add(gid)
            except Exception as exc:
                report['errors'].append(f'game {gid}: {str(exc)[:130]}')
        diagnostics['source'] = 'MLB official completed game boxscores' if added else diagnostics['source']
        diagnostics['prior_verified_starts_after'] = len(before) + len(added)
        diagnostics['status'] = ('verified starter history' if len(before) + len(added) >= MIN_VERIFIED_STARTS
                                 else 'limited or unavailable verified starts')
    if new_rows:
        write_merged(data_dir, new_rows, new_people)
    report['status'] = ('complete' if all(
        rec['prior_verified_starts_after'] >= MIN_VERIFIED_STARTS
        for rec in report['sides'].values()) else 'partial')
    report['errors'] = report['errors'][:8]
    return report
