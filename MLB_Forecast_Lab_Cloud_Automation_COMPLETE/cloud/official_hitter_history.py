"""Verified pregame batter-only 2026 historical game logs from the MLB API.

No current-date or future batting stats are ever used. Independent 60-game
samples are read before creating a new forecast; saved pregame snapshots are
not modified. This feeds the existing *uncalibrated*, bounded lineup overlay.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

GAME_TYPES = {"R", "F", "D", "L", "W"}
MAX_PRIOR_GAMES = 60
URL = "https://statsapi.mlb.com/api/v1/people/{pid}/stats"


def _get(url):
    req = Request(url, headers={"User-Agent": "MLB Forecast Lab pregame hitter context/1.0"})
    with urlopen(req, timeout=18) as response:
        return json.load(response)


def _integer(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def prior_hitter_profile(player_id, game_day, *, fetcher=None):
    """Return 2026 regular/playoff PA and shrunk batter weights strictly before game_day."""
    day = date.fromisoformat(str(game_day)[:10])
    pid = int(player_id)
    if pid <= 0:
        raise ValueError("Invalid MLB player identifier")
    q = urlencode({"stats": "gameLog", "group": "hitting", "season": day.year,
                   "sportIds": 1, "gameType": ",".join(sorted(GAME_TYPES))})
    fetch = fetcher or _get
    response = fetch(URL.format(pid=pid) + "?" + q)
    if not isinstance(response, dict) or not isinstance(response.get("stats"), list):
        raise ValueError("Malformed MLB hitter game-log response")
    by_game = {}
    for block in response["stats"]:
        for split in block.get("splits", []):
            if not isinstance(split, dict):
                continue
            raw_day = split.get("date")
            try:
                played = date.fromisoformat(str(raw_day)[:10])
            except (TypeError, ValueError):
                continue
            if played >= day or played.year != day.year or split.get("gameType") not in GAME_TYPES:
                continue
            stat = split.get("stat") or {}
            if not isinstance(stat, dict):
                continue
            ab = _integer(stat.get("atBats"))
            bb = _integer(stat.get("baseOnBalls"))
            hbp = _integer(stat.get("hitByPitch"))
            sf = _integer(stat.get("sacFlies"))
            pa = ab + bb + hbp + sf
            if pa <= 0 or pa > 15:
                continue
            hits = _integer(stat.get("hits"))
            doubles = _integer(stat.get("doubles"))
            triples = _integer(stat.get("triples"))
            homeruns = _integer(stat.get("homeRuns"))
            if hits > ab or doubles + triples + homeruns > hits:
                continue
            singles = hits - doubles - triples - homeruns
            weighted = (.69 * bb + .72 * hbp + .89 * singles +
                        1.27 * doubles + 1.62 * triples + 2.10 * homeruns)
            game_id = str((split.get("game") or {}).get("gamePk") or "")
            if not game_id.isdigit():
                continue
            key = (played.isoformat(), game_id)
            if key in by_game and by_game[key] != (pa, weighted):
                raise ValueError("Contradictory official hitter game logs")
            by_game[key] = (pa, weighted)
    chosen = sorted(by_game.items(), key=lambda x: x[0])[-MAX_PRIOR_GAMES:]
    appearances = sum(plate for _, (plate, _) in chosen)
    runs_weighted = sum(weight for _, (_, weight) in chosen)
    return {"id": pid, "observed_pa": appearances,
            "estimated_woba": (runs_weighted + 150 * .320) / (appearances + 150),
            "games": len(chosen), "source": "Official MLB hitter game logs",
            "cutoff_exclusive": day.isoformat()}


def collect_verified_lineup_history(snapshot, game_day, *, fetcher=None, max_workers=6):
    """Collect 18 independent player logs; fail closed to neutral if any API is incomplete."""
    lineups = (snapshot or {}).get("confirmed_lineups") or {}
    confirmed = (snapshot or {}).get("is_official_lineup") or {}
    if any(not confirmed.get(side) or len(lineups.get(side, [])) != 9
           for side in ("home", "away")):
        return {"status": "official_lineups_incomplete", "by_side": {}, "prior_pa": {}}
    expected = {}
    for side in ("home", "away"):
        ids = [int(p.get("id") or 0) for p in lineups[side]]
        if any(pid <= 0 for pid in ids) or len(set(ids)) != 9:
            return {"status": "invalid_official_lineup_ids", "by_side": {}, "prior_pa": {}}
        expected[side] = ids
    observed = {}
    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(prior_hitter_profile, pid, game_day, fetcher=fetcher): pid
                   for pid in sorted(set(expected["home"] + expected["away"]))}
        for future in as_completed(futures):
            pid = futures[future]
            try:
                observed[pid] = future.result()
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append({"player_id": pid, "reason": str(exc)[:140]})
    if errors or len(observed) != len(set(expected["home"] + expected["away"])):
        return {"status": "official_history_unavailable", "by_side": {},
                "prior_pa": {}, "errors": errors[:18]}
    by_side = {side: [observed[i] for i in expected[side]] for side in ("home", "away")}
    return {"status": "verified_earlier_date_hitter_logs", "by_side": by_side,
            "prior_pa": {side: sum(v["observed_pa"] for v in by_side[side])
                         for side in ("home", "away")},
            "features_cutoff_exclusive": str(game_day)[:10],
            "source": "Official MLB 2026 hitting game logs, up to last 60 prior games per batter",
            "limitations": "Lineup strength overlay is experimental and not independently calibrated"}
