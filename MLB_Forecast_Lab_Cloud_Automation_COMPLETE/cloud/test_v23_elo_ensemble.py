"""V23 correctness, leakage and honest paired-model reporting regressions."""
import copy
import math
import unittest
from datetime import datetime, timedelta, timezone

from cloud.v23_elo_ensemble import NAME, freeze
from cloud.v17_prospective import score_originals


KICKOFF = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)


def sample(game_id="100", *, home_win=.7, elo=.5, frozen=True, final=(4, 2),
           lead_minutes=20, kind="original_pregame"):
    row = {
        "game_id": str(game_id), "date": "2026-10-15",
        "forecast_kind": kind,
        "forecast_created_utc": (KICKOFF - timedelta(minutes=lead_minutes)).isoformat(),
        "game_start_utc": KICKOFF.isoformat(),
        "home": "LAN", "away": "MIL",
        "predicted_home_win": home_win, "elo_home_win": elo,
        "expected_runs": {"total": 7.4},
        "total_distribution": {"4": .2, "6": .4, "10": .4},
        "official_final": {"home": final[0], "away": final[1]},
    }
    if frozen:
        row["research_winner_ensemble"] = freeze(home_win, elo)
    return row


class FrozenEnsembleTests(unittest.TestCase):
    def test_fixed_weight_no_inputs_from_final(self):
        self.assertEqual(freeze(.8, .4)["home_win_probability"], .6)
        self.assertEqual(freeze(.8, .4)["method"], NAME)
        for bad in (float("nan"), float("inf"), -0.01, 1.01, None, True):
            with self.subTest(value=str(bad)):
                with self.assertRaises(ValueError):
                    freeze(bad, .5)

    def test_matched_brier_and_accuracy_against_both_baselines(self):
        # Case 1: home wins; 0.7 main, 0.5 Elo, 0.6 blend.
        # Case 2: away wins; 0.7 main, 0.3 Elo, 0.5 blend.
        a = sample("a", home_win=.7, elo=.5, final=(4, 2))
        b = sample("b", home_win=.7, elo=.3, final=(1, 4))
        report = score_originals([a, b])["winner_ensemble_shadow_v23"]
        self.assertEqual(report["n"], 2)
        self.assertEqual(report["original"]["winner_correct"], 1)
        self.assertEqual(report["elo"]["winner_correct"], 1)
        self.assertEqual(report["fixed_50_50_blend"]["winner_correct"], 1)
        self.assertAlmostEqual(report["original"]["brier"], .29)
        self.assertAlmostEqual(report["elo"]["brier"], .17)
        self.assertAlmostEqual(report["fixed_50_50_blend"]["brier"], .305)
        self.assertFalse(report["production_forecasts_changed"])

    def test_missing_or_forged_shadow_never_backfilled_after_final(self):
        a = sample("a", frozen=False)
        b = sample("b")
        corrupted = copy.deepcopy(b)
        corrupted["game_id"] = "corrupt"
        corrupted["research_winner_ensemble"]["home_win_probability"] = .99
        report = score_originals([a, b, corrupted])["winner_ensemble_shadow_v23"]
        self.assertEqual(report["n"], 1)
        self.assertEqual(report["excluded"]["missing_frozen_candidate"], 1)
        self.assertEqual(report["excluded"]["invalid_frozen_candidate"], 1)
        self.assertEqual(report["fixed_50_50_blend"]["brier"], .16)

    def test_late_preview_and_revisions_never_become_originals(self):
        rows = [
            sample("a"),
            sample("late", lead_minutes=-1),
            sample("preview", kind="preliminary_pregame"),
            sample("revision", kind="revised_pregame"),
        ]
        scored = score_originals(rows)
        self.assertEqual(scored["unique_originals"], 1)
        self.assertEqual(scored["winner_ensemble_shadow_v23"]["n"], 1)

    def test_original_brier_and_win_pick_do_not_change_with_shadow(self):
        with_shadow = score_originals([sample("a")])
        without_shadow = score_originals([sample("a", frozen=False)])
        self.assertEqual(with_shadow["winner"], without_shadow["winner"])
        self.assertEqual(with_shadow["winner"]["brier"], .09)
        self.assertEqual(without_shadow["winner_ensemble_shadow_v23"]["n"], 0)

    def test_wrong_formula_or_weights_rejected(self):
        rows = [sample("a"), sample("b")]
        rows[0]["research_winner_ensemble"]["elo_weight"] = .2
        rows[1]["research_winner_ensemble"]["method"] = "tuned_after_outcomes"
        report = score_originals(rows)["winner_ensemble_shadow_v23"]
        self.assertEqual(report["n"], 0)
        self.assertEqual(report["excluded"]["invalid_frozen_candidate"], 2)


if __name__ == "__main__":
    unittest.main()
