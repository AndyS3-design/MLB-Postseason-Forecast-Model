"""V25 fixed V23 model/Elo blend: untouched retrospective 30-game test.

Requires the ORIGINAL previously archived V20 2026 replay artifact. Formula
was frozen in V23 before this audit; no fitting, weight searching or
reconstruction of old unrecorded joint probabilities.
"""
from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path

from cloud.v22_accuracy_gate import evaluate as validate_all_30
from cloud.v23_elo_ensemble import freeze, MODEL_WEIGHT


def score(series):
    n=len(series)
    if n==0:raise ValueError("Empty cohort")
    probs=[p for p,y in series]
    actual=[y for p,y in series]
    return {
        "n":n,
        "correct_winners":sum(int((p>=.5)==bool(y)) for p,y in series),
        "winner_accuracy":round(sum(int((p>=.5)==bool(y)) for p,y in series)/n,4),
        "brier":round(sum((p-y)**2 for p,y in series)/n,6),
        "mean_confidence":round(sum(max(p,1-p) for p in probs)/n,6),
    }


def run(rows):
    rows=list(rows)
    validated=validate_all_30(rows)
    paired={"original":[],"elo":[],"v23_fixed_blend":[]}
    diffs=[]
    for row in rows:
        y=int(int(row["actual_home_runs"])>int(row["actual_away_runs"]))
        main=float(row["home_win_probability"])
        elo=float(row["elo_home_win_probability"])
        mix=freeze(main,elo)["home_win_probability"]
        paired["original"].append((main,y))
        paired["elo"].append((elo,y))
        paired["v23_fixed_blend"].append((mix,y))
        diffs.append({"game_id":str(row["game_id"]),"date":str(row["date"]),
            "main_home_win":round(main,6),"elo_home_win":round(elo,6),
            "fixed_blend_home_win":round(mix,6),
            "model_pick": "home" if main>=.5 else "away",
            "blend_pick":"home" if mix>=.5 else "away",
            "actual_winner":"home" if y else "away"})
    all_metrics={name:score(item) for name,item in paired.items()}
    mix=all_metrics["v23_fixed_blend"]
    main=all_metrics["original"]
    elo=all_metrics["elo"]
    assert main["correct_winners"]==validated["winner_correct"]
    assert elo["correct_winners"]==validated["elo_winners_correct"]
    return {
        "study":"2026 thirty-game V23 fixed ensemble retrospective check",
        "retrospective_only":True,
        "out_of_sample_accuracy_claim_allowed":False,
        "tuning_using_2026_results":False,
        "engine_original":"18.0.0-forecast-integrity",
        "weight_precommitted_from_v23":MODEL_WEIGHT,
        "games":30,"target_accuracy":0.9,"target_correct_games":27,
        "predictions":all_metrics,
        "v23_minus_main_brier":round(mix["brier"]-main["brier"],6),
        "v23_minus_elo_brier":round(mix["brier"]-elo["brier"],6),
        "v23_pick_changes_vs_main":sum(d["model_pick"]!=d["blend_pick"] for d in diffs),
        "v23_met_numeric_90pct_on_retrospective_games":mix["correct_winners"]>=27,
        "requires_fresh_forward_games_before_promoting":True,
        "sources":["Exact archived V20 30-game pregame feature cutoff research artifact",
                   "V22 all-game audit", "V23 predeclared 50/50 formula"],
        "warning":"All candidate probabilities are calculated on historical replay (not actually recorded V23 pregame). Never claim this is prospective, optimize its weight from these finals, or advertise 90% live winner skill.",
        "per_game_diagnostics":sorted(diffs,key=lambda item:(item["date"],item["game_id"])),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--replay",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    with args.replay.open(newline="",encoding="utf-8-sig") as f:
        report=run(csv.DictReader(f))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print("V25_FIXED_BLEND_COMPARISON",json.dumps(report["predictions"],sort_keys=True))
    print("V25_FIXED_BLEND_DELTAS",json.dumps({
        "delta_vs_original":report["v23_minus_main_brier"],
        "delta_vs_elo":report["v23_minus_elo_brier"],
        "pick_changes_vs_original":report["v23_pick_changes_vs_main"],
        "target_met":report["v23_met_numeric_90pct_on_retrospective_games"]},sort_keys=True))
    print("V25_REPORT",args.out)


if __name__=="__main__":
    main()
