"""Bounded pregame holding pattern for delayed best-effort GitHub cron.

Never generates or modifies a forecast. The scientific worker independently
enforces its original 8-30 minute cutoff and rejects games already started.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from cloud import preflight

UTC = timezone.utc
TARGET_LEAD_MINUTES = 29.0
MAX_WAIT_MINUTES = 240
POLL_SECONDS = 300


def _official_games(now, fetcher):
    found = {}
    for _, game in preflight._schedule_games(now, fetcher):
        gid = str(game.get('gamePk') or '')
        if gid.isdigit() and gid not in found:
            found[gid] = game
    return found


def await_window(game_ids, fetcher=None, clock=None, sleeper=None,
                 max_wait_minutes=MAX_WAIT_MINUTES):
    """Wait until the nearest confirmed game is within its safe final window.

    Recheck official dates and game state during the wait. Fail visibly rather
    than silently marking a missed/pushed game as forecasted.
    """
    wanted = {str(g).strip() for g in game_ids if str(g).strip()}
    if not wanted or any(not g.isdigit() for g in wanted):
        raise ValueError('Explicit numeric official MLB game IDs are required')
    fetcher = fetcher or preflight.fetch_schedule
    clock = clock or (lambda: datetime.now(UTC))
    sleeper = sleeper or time.sleep
    started = clock()
    if started.tzinfo is None:
        raise ValueError('UTC-aware clock required')
    deadline = started + timedelta(minutes=max_wait_minutes)
    while True:
        now = clock()
        if now >= deadline:
            raise TimeoutError('No verified pregame final window before wait deadline')
        games = _official_games(now, fetcher)
        upcoming = []
        for gid in wanted:
            game = games.get(gid)
            if game is None:
                raise RuntimeError('Expected official game missing: ' + gid)
            if game.get('gameType') not in preflight.GAME_TYPES:
                raise RuntimeError('Expected game is not a regular/postseason MLB game: ' + gid)
            state = str((game.get('status') or {}).get('detailedState') or '').strip().lower()
            if state not in preflight.ALLOWED_STATES:
                raise RuntimeError('Game status no longer permits a pregame prediction: ' + gid + ' (' + state + ')')
            start = datetime.fromisoformat(str(game['gameDate']).replace('Z', '+00:00'))
            if start.tzinfo is None:
                raise ValueError('Missing official game start timezone')
            lead = (start - now).total_seconds() / 60
            if lead < 8:
                raise RuntimeError('Verified final forecast window already expired: ' + gid)
            upcoming.append((lead, gid))
        lead, gid = min(upcoming)
        if lead <= 30:
            print('Verified pregame window reached for MLB game ' + gid
                  + ' (' + format(lead, '.1f') + ' minutes before scheduled start)', flush=True)
            return gid
        seconds = min(POLL_SECONDS, max(1, (lead - TARGET_LEAD_MINUTES) * 60),
                      (deadline - now).total_seconds())
        print('Awaiting verified pregame window; next game ' + gid
              + ' starts in ' + format(lead, '.1f') + ' minutes', flush=True)
        sleeper(seconds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--game-ids', required=True)
    args = p.parse_args()
    await_window(args.game_ids.split(','))


if __name__ == '__main__':
    main()
