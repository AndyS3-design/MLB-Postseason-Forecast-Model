"""V30 read-only, official-denominator prospective MLB scorecard.

Predeclared cohort starts 2026-10-14. Missing forecasts count as wrong.
Every graded forecast must match its first pre-first-pitch GitHub commit.
No 2026 fitting, no synthesized joint probabilities, no production writes.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from cloud.v28_first_commit_provenance import github_get, verify_one

START = date(2026, 10, 14)
TYPES = frozenset(("F", "D", "L", "W"))
LINES = (4.5, 5.5)
API = "https://statsapi.mlb.com/api/v1/schedule"
FEED = "https://statsapi.mlb.com/api/v1.1/game/{}/feed/live"


def day(value):
    return date.fromisoformat(str(value)[:10])


def instant(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)


def prob(value):
    if isinstance(value, bool):
        raise ValueError("Boolean probability")
    x = float(value)
    if not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("Invalid probability")
    return x


def score(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("Invalid official score")
    n = int(value)
    if n < 0 or str(n) != str(value):
        raise ValueError("Invalid official score")
    return n


def fetch_json(url):
    with urlopen(Request(url, headers={"User-Agent": "MLB V30 independent audit"}), timeout=35) as response:
        return json.load(response)


def fetch_schedule(as_of):
    params = urlencode({"sportId": 1, "startDate": START.isoformat(),
                        "endDate": (as_of - timedelta(days=1)).isoformat(),
                        "gameTypes": ",".join(sorted(TYPES)), "hydrate": "linescore"})
    return fetch_json(API + "?" + params)


def official_games(schedule, as_of, fetch_feed):
    """Every completed official postseason game, including scoreless Finals.

    A complete duplicate is authoritative; unresolved scoreless finals are
    recovered only from the official game feed, or cause a hard failure.
    """
    if not isinstance(schedule, dict) or not isinstance(schedule.get("dates"), list):
        raise ValueError("Malformed official schedule")
    found, unresolved = {}, {}
    for block in schedule["dates"]:
        if not isinstance(block, dict) or not isinstance(block.get("games"), list):
            raise ValueError("Malformed official date block")
        for g in block["games"]:
            if not isinstance(g, dict) or g.get("gameType") not in TYPES:
                continue
            if (not isinstance(g.get("status"), dict) or
                    g["status"].get("abstractGameState") != "Final"):
                continue
            gid = str(g.get("gamePk", ""))
            if not gid.isdigit():
                raise ValueError("Final missing game ID")
            d = day(g.get("officialDate") or block.get("date"))
            if not START <= d < as_of:
                continue
            teams = g.get("teams") or {}
            try:
                h, a = score(teams["home"]["score"]), score(teams["away"]["score"])
                if h == a:
                    raise ValueError("Tied final")
            except (KeyError, TypeError, ValueError):
                unresolved.setdefault(gid, []).append((g, d))
                continue
            record = {"game_id": gid, "date": d.isoformat(), "home": h, "away": a,
                      "game_start_utc": g.get("gameDate"),
                      "home_team_id": teams.get("home", {}).get("team", {}).get("id"),
                      "away_team_id": teams.get("away", {}).get("team", {}).get("id")}
            if gid in found and any(found[gid][k] != record[k]
                                     for k in ("date", "home", "away")):
                raise ValueError("Conflicting official final " + gid)
            found[gid] = record
    for gid, entries in sorted(unresolved.items()):
        if gid in found:
            continue
        feed = fetch_feed(gid)
        data = feed["gameData"]
        if str(data["game"]["pk"]) != gid or data["status"]["abstractGameState"] != "Final":
            raise ValueError("Official game feed identity or status mismatch " + gid)
        d = day(data["datetime"]["officialDate"])
        if any(d != entry_day for _, entry_day in entries):
            raise ValueError("Official game feed date mismatch " + gid)
        runs = feed["liveData"]["linescore"]["teams"]
        h, a = score(runs["home"]["runs"]), score(runs["away"]["runs"])
        if h == a:
            raise ValueError("Tied recovered official final " + gid)
        for g, _ in entries:
            for side in ("home", "away"):
                tid = (g.get("teams", {}).get(side, {}).get("team") or {}).get("id")
                if tid is not None and int(tid) != int(data["teams"][side]["id"]):
                    raise ValueError("Official feed team mismatch " + gid)
        g = entries[0][0]
        found[gid] = {"game_id": gid, "date": d.isoformat(), "home": h, "away": a,
                      "game_start_utc": g.get("gameDate"),
                      "home_team_id": g.get("teams", {}).get("home", {}).get("team", {}).get("id"),
                      "away_team_id": g.get("teams", {}).get("away", {}).get("team", {}).get("id")}
    return sorted(found.values(), key=lambda x: (x["date"], x["game_id"]))


def historical(rows):
    totals, years, ids = [], set(), set()
    for r in rows:
        y, gid = int(r["year"]), str(r["game_id"])
        if y not in range(2020, 2026) or gid in ids:
            raise ValueError("Historical baseline year/ID invalid")
        ids.add(gid)
        years.add(y)
        t = score(r["total_runs"])
        if t != score(r["home_runs"]) + score(r["away_runs"]):
            raise ValueError("Historical score conflict")
        totals.append(t)
    if years != set(range(2020, 2026)):
        raise ValueError("Incomplete older-year baseline")
    return {"n": len(totals), "mean": sum(totals) / len(totals),
            "over": {str(line): sum(t > line for t in totals) / len(totals)
                     for line in LINES}}


def metrics(pairs):
    n = len(pairs)
    return {"n": n, "correct": sum(int((p >= .5) == bool(y)) for p, y in pairs),
            "accuracy": round(sum(int((p >= .5) == bool(y)) for p, y in pairs) / n, 6) if n else None,
            "brier": round(sum((p - y) ** 2 for p, y in pairs) / n, 6) if n else None}


def validate(record, game, *, verifier):
    if (record.get("forecast_kind") != "original_pregame" or
            str(record.get("game_id")) != game["game_id"] or
            record.get("date") != game["date"] or
            not record.get("home") or not record.get("away") or
            record["home"] == record["away"]):
        raise ValueError("Original identity mismatch")
    created = instant(record["forecast_created_utc"])
    start = instant(record["game_start_utc"])
    if not created < start or (game.get("game_start_utc") and
                               not created < instant(game["game_start_utc"])):
        raise ValueError("Original not pre-first-pitch")
    if "official_final" in record:
        final = record["official_final"]
        if score(final["home"]) != game["home"] or score(final["away"]) != game["away"]:
            raise ValueError("Official settlement conflict")
    m, e = prob(record["predicted_home_win"]), prob(record["elo_home_win"])
    verifier(record, game["game_id"] + ".json")
    blend = record.get("research_winner_ensemble") or {}
    if blend.get("method") != "v23_fixed_50_model_50_elo":
        raise ValueError("Missing genuine frozen V23")
    v = prob(blend["home_win_probability"])
    if (prob(blend["model_weight"]) != .5 or prob(blend["elo_weight"]) != .5 or
            not math.isclose(v, (m + e) / 2, abs_tol=1e-10, rel_tol=0)):
        raise ValueError("Invalid frozen V23")
    return m, e, v


def grade(games, records, baseline, *, as_of, verifier):
    if len({g["game_id"] for g in games}) != len(games):
        raise ValueError("Duplicate official game")
    pairs = {"original": [], "elo": [], "v23": []}
    totals, joints = {str(x): [] for x in LINES}, {str(x): [] for x in LINES}
    expected_errors, baseline_errors, missing, invalid = [], [], [], []
    correct_full = 0
    for g in games:
        gid = g["game_id"]
        if gid not in records:
            missing.append(gid)
            continue
        r = records[gid]
        try:
            m, e, v = validate(r, g, verifier=verifier)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            invalid.append({"game_id": gid, "reason": str(exc)})
            continue
        y = int(g["home"] > g["away"])
        correct_full += int((m >= .5) == bool(y))
        for name, p in (("original", m), ("elo", e), ("v23", v)):
            pairs[name].append((p, y))
        pmf = r.get("total_distribution") or {}
        try:
            dist = {int(k): prob(p) for k, p in pmf.items()}
            if not dist or len(dist) != len(pmf) or abs(sum(dist.values()) - 1) > 1e-6:
                raise ValueError("Invalid total PMF")
            expected = float(r["expected_runs"]["total"])
            if not math.isfinite(expected) or expected < 0:
                raise ValueError("Invalid expected total")
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        actual = g["home"] + g["away"]
        expected_errors.append(abs(actual - expected))
        baseline_errors.append(abs(actual - baseline["mean"]))
        for line in LINES:
            key = str(line)
            over = sum(p for t, p in dist.items() if t > line)
            target = int(actual > line)
            totals[key].append((over, target))
            raw = (r.get("win_and_over_probabilities") or {}).get(key)
            if not isinstance(raw, dict):
                continue
            try:
                h, a = prob(raw["home_win_and_over"]), prob(raw["away_win_and_over"])
                fav = "home" if m >= .5 else "away"
                joint = prob(raw["favorite_win_and_over"])
                if (raw.get("favorite_side") != fav or
                        abs(h + a - over) > 1e-6 or
                        abs(prob(raw["over"]) - over) > 1e-6 or
                        abs(joint - (h if fav == "home" else a)) > 1e-6):
                    continue
                joints[key].append((joint, int(bool(target) and
                                              (bool(y) == (fav == "home")))))
            except (KeyError, ValueError, TypeError):
                continue
    n = len(games)
    report = {"study": "V30 official prospective cohort (read-only)",
              "tracking_start": START.isoformat(), "as_of_exclusive_et": as_of.isoformat(),
              "official_completed_games": n, "valid_frozen_originals": len(pairs["original"]),
              "missing_ids": missing, "invalid_originals": invalid,
              "correct_full_cohort": correct_full,
              "full_cohort_accuracy": round(correct_full / n, 6) if n else None,
              "capture_rate": round(len(pairs["original"]) / n, 6) if n else None,
              "matched_winners": {k: metrics(v) for k, v in pairs.items()},
              "historical_baseline_games": baseline["n"],
              "total_run_mae": round(sum(expected_errors) / len(expected_errors), 6) if expected_errors else None,
              "historical_total_mae_same_games": round(sum(baseline_errors) / len(baseline_errors), 6) if baseline_errors else None,
              "over": {}, "same_simulation_joint": {},
              "forecast_weights_changed": False, "prospective_90pct_verified": False,
              "note": "Missing forecasts count as wrong; matched Brier only. Git first-commit provenance required. No 2026 fitting, no synthetic joint odds."}
    for line in LINES:
        key = str(line)
        report["over"][key] = {"original": metrics(totals[key]),
                               "older_year_constant": metrics([(baseline["over"][key], y)
                                                                for _, y in totals[key]])}
        report["same_simulation_joint"][key] = metrics(joints[key])
    return report


def run(root, repo, *, as_of, schedule=None, fetch_feed=None, get=None):
    as_of = day(as_of)
    if as_of <= START:
        raise ValueError("Invalid as-of date")
    root = Path(root)
    base = root if (root / "cloud_records").is_dir() else root / "MLB_Forecast_Lab_Cloud_Automation_COMPLETE"
    games = official_games(schedule if schedule is not None else fetch_schedule(as_of),
                           as_of, fetch_feed or (lambda gid: fetch_json(FEED.format(gid))))
    records = {}
    for path in sorted((base / "cloud_records" / "predictions").glob("*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        if str(r.get("game_id")) != path.stem:
            raise ValueError("Prediction filename/game ID mismatch")
        records[path.stem] = r
    with (base / "data" / "official_postseason_2020_2025.csv").open(newline="", encoding="utf-8") as f:
        baseline = historical(csv.DictReader(f))
    fetch = get or github_get
    return grade(games, records, baseline, as_of=as_of,
                 verifier=lambda r, name: verify_one(r, name, repo, fetch))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.repo:
        parser.error("--repo is required")
    as_of = day(args.as_of or datetime.now(ZoneInfo("America/New_York")).date())
    result = run(args.root, args.repo, as_of=as_of)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
