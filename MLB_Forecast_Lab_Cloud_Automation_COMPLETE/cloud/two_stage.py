"""Day-of-game preliminary previews and honest prospective paired evaluation.

Preliminary snapshots are frozen in cloud_records/preliminary/. The separate
cloud_records/predictions/ file remains the final original used for primary
metrics, V9 capture accounting, and prospective shadow challengers.
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
from cloud.v8_evaluate import valid_original, timestamp

ET = ZoneInfo("America/New_York")
EARLIEST_PREVIEW_HOUR_ET = 10
MIN_PRELIMINARY_LEAD_MINUTES = 45
PREVIEW_GAME_TYPES = {"R", "F", "D", "L", "W"}
PREGAME_STATES = {"scheduled", "pre-game", "pregame", "preview", "warmup"}


def eligible_preliminary(game_id, game_date, start_utc, game_type, status, now):
    """Start no earlier than 10 AM Eastern and finish at least 45 min pregame.

    The game's official day must be today in Eastern time; this must never
    fabricate a day-after-the-game snapshot or use a live-game score.
    """
    try:
        if now.tzinfo is None:
            return False
        start = timestamp(start_utc)
        if start.tzinfo is None:
            return False
        today = now.astimezone(ET)
        game_day = date.fromisoformat(str(game_date)[:10])
        return (
            str(game_id).isdigit()
            and str(game_type) in PREVIEW_GAME_TYPES
            and str(status or "").strip().lower() in PREGAME_STATES
            and game_day == today.date()
            and today.hour >= EARLIEST_PREVIEW_HOUR_ET
            and (start - now).total_seconds() / 60 >= MIN_PRELIMINARY_LEAD_MINUTES
        )
    except (KeyError, ValueError, TypeError, OverflowError):
        return False


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _identity(prelim, final):
    return all(str(prelim.get(k)) == str(final.get(k)) for k in
               ("game_id", "date", "home", "away", "game_start_utc"))


def paired_stage_metrics(root):
    """Evaluate only genuinely frozen, paired, settled original predictions.

    A preliminary without a final is still visible but is NEVER silently
    substituted into the original-prediction (official) accuracy denominator.
    """
    root = Path(root)
    previews = {}
    invalid = 0
    for path in sorted((root / "cloud_records/preliminary").glob("*.json")):
        record = _read(path)
        if (not isinstance(record, dict) or
                record.get("forecast_kind") != "preliminary_pregame" or
                str(record.get("game_id")) != path.stem or
                not valid_original(record)):
            invalid += 1
            continue
        previews[path.stem] = record
    originals = {}
    for path in sorted((root / "cloud_records/predictions").glob("*.json")):
        record = _read(path)
        if (isinstance(record, dict) and str(record.get("game_id")) == path.stem
                and valid_original(record)):
            originals[path.stem] = record

    paired = []
    for game_id, early in previews.items():
        final = originals.get(game_id)
        if not final or not _identity(early, final):
            continue
        try:
            if not timestamp(early["forecast_created_utc"]) < timestamp(final["forecast_created_utc"]):
                continue
        except (TypeError, ValueError, KeyError):
            continue
        if final.get("official_final"):
            paired.append((early, final))

    n = len(paired)
    sums = {
        "preliminary_winner_brier": 0., "final_winner_brier": 0.,
        "preliminary_total_mae": 0., "final_total_mae": 0.,
    }
    for early, final in paired:
        actual = final["official_final"]
        y = float(int(actual["home"]) > int(actual["away"]))
        runs = int(actual["home"]) + int(actual["away"])
        for prefix, record in (("preliminary", early), ("final", final)):
            sums[f"{prefix}_winner_brier"] += (float(record["predicted_home_win"]) - y) ** 2
            sums[f"{prefix}_total_mae"] += abs(float(record["expected_runs"]["total"]) - runs)
    return {
        "status": "awaiting_paired_finals" if not n else
                  "small_sample_exploratory" if n < 30 else "prospective_paired_comparison",
        "preliminary_count": len(previews),
        "final_original_count": len(originals),
        "preliminary_without_final_count": sum(gid not in originals for gid in previews),
        "invalid_preliminary_files": invalid,
        "paired_settled_games": n,
        **({k: round(v / n, 5) for k, v in sums.items()} if n else {}),
        "notes": "Paired comparisons only; final originals are the primary forecast. Small samples cannot establish improvement.",
    }
