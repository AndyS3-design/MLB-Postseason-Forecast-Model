"""Independent rolling reconciliation of the official MLB final schedule.

The existing V9 capture-rate denominator uses imported finals. If import fails,
that denominator can undercount. This second, explicitly date-limited audit
uses the official MLB schedule as the denominator, without modifying forecasts
or calculating a hindsight prediction.

The worker calls this only during full maintenance runs, never in the
time-sensitive fast pregame scoring path.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from cloud.refresh import API, all_finals, fetch_json
from cloud.v8_evaluate import valid_original
from cloud.v9_tracking import TRACKING_START, load_originals

GAME_TYPES = {"R", "F", "D", "L", "W"}
ROLLING_DAYS = 7
DETAIL_LIMIT = 20


def _date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def reconcile(root, as_of, *, days=ROLLING_DAYS, fetcher=None,
              tracking_start=TRACKING_START):
    """Cross-check yesterday and the prior days, never today's live games.

    A recognized final must have an official gamePk, officialDate and both
    final scores. Postponed, suspended, canceled and still-live games are
    excluded; an incomplete final is explicitly flagged, not counted as a
    missing prediction. Doubleheaders retain their separate MLB game IDs.
    """
    root = Path(root)
    as_of = _date(as_of)
    tracking_start = _date(tracking_start)
    if not isinstance(days, int) or not 1 <= days <= 31:
        raise ValueError("days must be an integer in 1..31")
    start = max(tracking_start, as_of - timedelta(days=days))
    out = {
        "source": "Independent official MLB schedule (not imported CSVs)",
        "tracking_start_date": tracking_start.isoformat(),
        "as_of_exclusive_et_date": as_of.isoformat(),
        "window_start_date": start.isoformat(),
        "window_days": days,
        "official_completed_games": 0,
        "official_games_with_valid_original": 0,
        "official_games_without_valid_original": 0,
        "official_capture_fraction": None,
        "completed_games_imported": 0,
        "import_coverage_fraction": None,
        "missing_imports": [],
        "missing_originals": [],
        "invalid_originals": [],
        "identity_or_score_conflicts": [],
        "official_finals_missing_scores": [],
        "status": "not_started",
        "notes": "Rolling operational audit, not a historical replay or proof of forecast accuracy.",
    }
    if start >= as_of:
        return out
    if fetcher is None:
        fetcher = fetch_json
    url = API + "?" + urlencode({
        "sportId": 1,
        "startDate": start.isoformat(),
        "endDate": (as_of - timedelta(days=1)).isoformat(),
        "gameTypes": ",".join(sorted(GAME_TYPES)),
    })
    payload = fetcher(url)
    if not isinstance(payload, dict) or not isinstance(payload.get("dates"), list):
        raise ValueError("Official MLB schedule response lacks dates array")
    games = {}
    incomplete = []
    for day in payload["dates"]:
        if not isinstance(day, dict) or not isinstance(day.get("games", []), list):
            raise ValueError("Official MLB schedule has an invalid date block")
        for g in day.get("games", []):
            if not isinstance(g, dict) or g.get("gameType") not in GAME_TYPES:
                continue
            if g.get("status", {}).get("abstractGameState") != "Final":
                continue
            game_id = str(g.get("gamePk") or "")
            raw_day = g.get("officialDate") or day.get("date")
            if not game_id.isdigit() or not raw_day:
                incomplete.append({"game_id": game_id, "reason": "Missing game ID or official date"})
                continue
            try:
                game_date = _date(raw_day)
            except (TypeError, ValueError):
                incomplete.append({"game_id": game_id, "reason": "Invalid official date"})
                continue
            if not start <= game_date < as_of:
                continue
            try:
                teams = g["teams"]
                away = int(teams["away"]["score"])
                home = int(teams["home"]["score"])
                if away < 0 or home < 0:
                    raise ValueError("Negative runs")
            except (TypeError, ValueError, KeyError):
                incomplete.append({"game_id": game_id, "reason": "Official final lacks final scores"})
                continue
            candidate = {"game_id": game_id, "date": game_date.isoformat(),
                         "away_final": away, "home_final": home}
            if game_id in games and games[game_id] != candidate:
                raise ValueError("Conflicting duplicate official final: " + game_id)
            games[game_id] = candidate

    originals, unreadable = load_originals(root)
    imported = all_finals(root)
    captured = 0
    imported_count = 0
    missing_originals = []
    invalid_originals = []
    missing_imports = []
    conflicts = []
    for game_id, g in sorted(games.items(), key=lambda pair: (pair[1]["date"], pair[0])):
        r = originals.get(game_id)
        if r is None:
            missing_originals.append({"game_id": game_id, "date": g["date"]})
        elif r.get("date") != g["date"] or not valid_original(r):
            invalid_originals.append({"game_id": game_id, "date": g["date"],
                                      "reason": "Invalid pre-first-pitch original or game date mismatch"})
        else:
            captured += 1
        f = imported.get(game_id)
        if f is None:
            missing_imports.append({"game_id": game_id, "date": g["date"]})
        else:
            try:
                same = (str(f["date"]) == g["date"]
                        and int(f["home_final"]) == g["home_final"]
                        and int(f["away_final"]) == g["away_final"])
            except (KeyError, TypeError, ValueError):
                same = False
            if same:
                imported_count += 1
            else:
                conflicts.append({"game_id": game_id, "date": g["date"],
                                  "reason": "Imported game date or final score disagrees with MLB"})
    n = len(games)
    out.update({
        "official_completed_games": n,
        "official_games_with_valid_original": captured,
        "official_games_without_valid_original": n - captured,
        "official_capture_fraction": round(captured / n, 4) if n else None,
        "completed_games_imported": imported_count,
        "import_coverage_fraction": round(imported_count / n, 4) if n else None,
        "missing_imports": missing_imports[:DETAIL_LIMIT],
        "missing_import_count": len(missing_imports),
        "missing_originals": missing_originals[:DETAIL_LIMIT],
        "missing_original_count": len(missing_originals),
        "invalid_originals": invalid_originals[:DETAIL_LIMIT],
        "invalid_original_count": len(invalid_originals),
        "identity_or_score_conflicts": conflicts[:DETAIL_LIMIT],
        "score_conflict_count": len(conflicts),
        "official_finals_missing_scores": incomplete[:DETAIL_LIMIT],
        "official_finals_missing_scores_count": len(incomplete),
        "unreadable_original_file_count": len(unreadable),
        "status": ("needs_attention" if missing_imports or missing_originals
                   or invalid_originals or conflicts or incomplete or unreadable
                   else "reconciled" if n else "no_official_finals_in_window"),
    })
    return out
