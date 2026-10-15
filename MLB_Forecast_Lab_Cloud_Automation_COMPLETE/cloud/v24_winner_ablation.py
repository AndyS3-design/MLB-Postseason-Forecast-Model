"""V24: chronological, no-pregame-starter-identity winner feature ablation.

Purpose: discover whether simple *genuinely lagged* run-form and rest features
beat a fixed Elo baseline for win probability. Selection ONLY on 2024 regular
games after 2023 training. 2025/2026 are reporting cohorts, never search
objectives. This is research, not a new production winner or a 90% claim.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from extended_eval import all_games
from matchup_model import feature_frame

ROOT = Path(__file__).resolve().parents[1]
TRAIN_YEAR = 2023
VALIDATE_YEAR = 2024
TEST_YEARS = (2025, 2026)
C_VALUES = (.003, .03, .3)
CANDIDATES = {
    "elo_plus_form": ("elo_logit", "offense_rpg40_diff", "run_allowed_diff"),
    "elo_plus_form_rest": ("elo_logit", "offense_rpg15_diff", "offense_rpg40_diff",
                           "run_allowed_diff", "rest_diff"),
    "elo_plus_form_rest_bullpen": (
        "elo_logit", "offense_rpg15_diff", "offense_rpg40_diff",
        "run_allowed_diff", "rest_diff", "bullpen_used3_diff", "bullpen_used7_diff"),
}
# Models deliberately omit same-day or retrospective announced starter identities,
# realized boxscore pitcher stats, contemporaneous weather and betting-market quotes.


def metrics(y, probability):
    y = np.asarray(y, dtype=float)
    p = np.asarray(probability, dtype=float)
    if len(y) == 0 or len(y) != len(p):
        raise ValueError("Invalid paired cohort")
    if (not np.isfinite(p).all() or (p < 0).any() or (p > 1).any()
            or not np.isin(y, (0, 1)).all()):
        raise ValueError("Invalid outcomes or probabilities")
    return {
        "n": int(len(y)),
        "correct": int(np.sum((p >= .5) == y)),
        "accuracy": round(float(np.mean((p >= .5) == y)), 6),
        "brier": round(float(np.mean((p - y) ** 2)), 7),
        "log_loss": round(float(-np.mean(
            y * np.log(np.clip(p, 1e-12, 1)) +
            (1 - y) * np.log(np.clip(1 - p, 1e-12, 1)))), 7),
    }


def subset(frame, year, game_type):
    return frame[(frame.year == year) & (frame.game_type == game_type)].copy()


def fit(train, features, c):
    if not set(features).issubset(train.columns):
        raise ValueError("Features missing")
    if any(name in features for name in ("y_home", "year", "date", "game_id")):
        raise ValueError("Outcome or identity leakage into training")
    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=c, max_iter=500, random_state=2024))
    pipe.fit(train[list(features)].to_numpy(dtype=float), train.y_home.to_numpy(dtype=int))
    return pipe


def validate_and_fit(frame):
    """Strict nested chronology: fit 2023; 2024 select; refit 2023-24."""
    tr = subset(frame, TRAIN_YEAR, "R")
    val = subset(frame, VALIDATE_YEAR, "R")
    if len(tr) < 2000 or len(val) < 2000:
        raise ValueError("Incomplete training / validation regular seasons")
    baseline = metrics(val.y_home, val.home_elo)
    choices = []
    for name, columns in CANDIDATES.items():
        for c in C_VALUES:
            model = fit(tr, columns, c)
            scores = metrics(val.y_home, model.predict_proba(val[list(columns)])[:, 1])
            choices.append({
                "name": name, "features": list(columns), "c": c,
                "validation": scores,
            })
    # Primary objective = Brier. Tie break = fewer parameters and weaker C.
    winner = min(choices, key=lambda item: (
        item["validation"]["brier"], len(item["features"]), item["c"], item["name"]))
    # Critical: never select an expanded feature model that lost to plain Elo
    # on the only designated tuning season. Report it, do not promote it.
    improve = winner["validation"]["brier"] < baseline["brier"]
    best_name = winner["name"] if improve else "elo_only"
    training = frame[(frame.year.isin((TRAIN_YEAR, VALIDATE_YEAR))) &
                     (frame.game_type == "R")]
    champion = (fit(training, winner["features"], winner["c"]) if improve else None)
    return {"selected": best_name, "elo_validation": baseline,
            "winning_candidate": winner, "all_candidates": choices,
            "train_regular_games": len(tr), "validation_regular_games": len(val),
            "refit_regular_games": len(training),
            "train_years": [TRAIN_YEAR, VALIDATE_YEAR],
            "test_years_excluded_from_selection": list(TEST_YEARS),
            "selection_uses_2025_or_2026_results": False}, champion


def score_cohorts(frame, selected, fitted):
    scores = {}
    for year in TEST_YEARS:
        for kind in ("R", "P"):
            rows = subset(frame, year, kind)
            label = str(year) + ("_regular" if kind == "R" else "_postseason")
            if rows.empty:
                scores[label] = {"n": 0, "status": "not_available"}
                continue
            baseline = metrics(rows.y_home, rows.home_elo)
            pred = (fitted.predict_proba(rows[selected["winning_candidate"]["features"]])[:, 1]
                    if fitted is not None else rows.home_elo.to_numpy(dtype=float))
            result = metrics(rows.y_home, pred)
            scores[label] = {
                "n": len(rows), "elo": baseline, "selected_candidate": result,
                "brier_delta_candidate_minus_elo": round(
                    result["brier"] - baseline["brier"], 7),
                "different_winner_picks_vs_elo": int(np.sum(
                    (np.asarray(pred) >= .5) != (rows.home_elo.to_numpy() >= .5))),
                "status": "retrospective_diagnostic_not_live_forward_accuracy",
            }
    return scores


def run(data_dir):
    games = [g for g in all_games(Path(data_dir), True) if int(g["year"]) <= 2026]
    # No same-day pitching detail attachment. The selected features cannot
    # include starter/boxscore columns from the historical final-game archive.
    frame = feature_frame(games)
    info, fitted = validate_and_fit(frame)
    return {
        "status": "research_only_not_production_approved",
        "feature_origin": "rolling priors strictly before each game date",
        "data_source": "Retrosheet game logs + locally archived official MLB postseason games",
        "game_rows": len(frame),
        "training_and_selection": info,
        "retrospective_reporting_not_used_for_selection":
            score_cohorts(frame, info, fitted),
        "full_sample_accuracy_90pct_achieved": False,
        "production_model_modified": False,
        "limitations": [
            "2025 and 2026 have influenced earlier project development, so these are NOT untouched scientific holdouts.",
            "2026 postseason can expand as new finals are archived; historical scores cannot be sold as prospective.",
            "This candidate uses Elo and team run-form/rest ONLY; pitcher identity and new lineups are intentionally excluded.",
            "Even an improvement in historical Brier does not prove a profitable market edge or future 90 percent winner accuracy.",
        ],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=ROOT / "data")
    p.add_argument("--out", type=Path, default=ROOT / "outputs/v24_research/winner_ablation.json")
    a = p.parse_args()
    report = run(a.data_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("V24_SELECTION", json.dumps(report["training_and_selection"]["winning_candidate"], sort_keys=True))
    print("V24_WINNER_COHORTS", json.dumps(report["retrospective_reporting_not_used_for_selection"], sort_keys=True))
    print("V24_RESEARCH_REPORT", a.out)


if __name__ == "__main__":
    main()
