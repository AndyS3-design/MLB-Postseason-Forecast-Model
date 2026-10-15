"""V23 prespecified 50/50 model-Elo winner challenger.

This is a RESEARCH-ONLY prediction, recorded in the same immutable pregame
original as the production pick. The single fixed weight is not optimized on
2026 postseason finals. Do not use this candidate as a new production pick
until independent prospective evidence supports a promotion.
"""
from __future__ import annotations

import math
from collections import defaultdict

NAME = "v23_fixed_50_model_50_elo"
MODEL_WEIGHT = 0.5


def _probability(value):
    # Reject booleans, NaN, infinities and malformed probabilities.
    if isinstance(value, bool):
        raise ValueError("Boolean is not a probability")
    try:
        p = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Invalid probability") from error
    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
        raise ValueError("Invalid probability")
    return p


def freeze(model_home_win, elo_home_win):
    """Calculate a fixed out-of-sample shadow from *pregame* inputs only."""
    model = _probability(model_home_win)
    elo = _probability(elo_home_win)
    return {
        "method": NAME,
        "home_win_probability": MODEL_WEIGHT * model + (1.0 - MODEL_WEIGHT) * elo,
        "model_weight": MODEL_WEIGHT,
        "elo_weight": 1.0 - MODEL_WEIGHT,
        "role": "prospective_research_only_production_pick_unchanged",
    }


def _validated_shadow(record, model, elo):
    saved = record.get("research_winner_ensemble")
    if saved is None:
        return None, "missing_frozen_candidate"
    if not isinstance(saved, dict) or saved.get("method") != NAME:
        return None, "invalid_frozen_candidate"
    try:
        candidate = _probability(saved["home_win_probability"])
        model_weight = _probability(saved["model_weight"])
        elo_weight = _probability(saved["elo_weight"])
    except (KeyError, ValueError):
        return None, "invalid_frozen_candidate"
    expected = MODEL_WEIGHT * model + (1.0 - MODEL_WEIGHT) * elo
    if (model_weight != MODEL_WEIGHT or elo_weight != 1.0 - MODEL_WEIGHT
            or not math.isclose(candidate, expected, abs_tol=1e-10, rel_tol=0.0)):
        return None, "invalid_frozen_candidate"
    return candidate, None


def grade_paired_settled(settled):
    """Score on the SAME strictly valid pregame originals as v17 winner audit.

    Each row is the v17 validated tuple (record, home, away, total, pmf,
    original_probability, expected_total, elo_probability). Legacy snapshots
    without a pregame-frozen shadow never acquire a synthetic one afterward.
    """
    paired = []
    excluded = defaultdict(int)
    for row in settled:
        record, home, away, _, _, model, _, elo = row
        candidate, why = _validated_shadow(record, model, elo)
        if why is not None:
            excluded[why] += 1
            continue
        paired.append((record, int(home > away), model, elo, candidate))
    n = len(paired)
    result = {
        "method": NAME,
        "status": "no_frozen_challenger_games" if n == 0 else (
            "exploratory_small_sample" if n < 30 else "prospective_descriptive_only"),
        "n": n,
        "excluded": dict(excluded),
        "production_forecasts_changed": False,
        "warning": "Never refit on the 2026 postseason; 30 games or a high pick percentage alone cannot establish a reliable betting edge.",
    }
    if not n:
        return result
    def scored(column):
        ps = [x[column] for x in paired]
        return {
            "winner_correct": sum((p >= 0.5) == bool(row[1]) for p, row in zip(ps, paired)),
            "winner_accuracy": round(sum((p >= 0.5) == bool(row[1]) for p, row in zip(ps, paired)) / n, 4),
            "brier": round(sum((p - row[1]) ** 2 for p, row in zip(ps, paired)) / n, 6),
        }
    main = scored(2)
    elo = scored(3)
    blend = scored(4)
    result.update({
        "unique_pregame_dates": len({r[0].get("date") for r in paired}),
        "original": main,
        "elo": elo,
        "fixed_50_50_blend": blend,
        "blend_minus_original_brier": round(blend["brier"] - main["brier"], 6),
        "blend_minus_elo_brier": round(blend["brier"] - elo["brier"], 6),
        "different_winner_picks_from_original": sum((r[2] >= 0.5) != (r[4] >= 0.5) for r in paired),
        "note": "Scores compare identical frozen, settled games. A positive Brier delta means the blend was worse. No challenger promotion based on this cohort.",
    })
    return result
