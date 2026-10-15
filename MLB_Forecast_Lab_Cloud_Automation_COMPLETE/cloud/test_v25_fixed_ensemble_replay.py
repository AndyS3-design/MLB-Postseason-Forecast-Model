"""V25: preserve exactly 30 2026 games and predeclared blend coefficient."""
import unittest

from cloud.test_v22_accuracy_gate import row
from cloud.v25_fixed_ensemble_replay import run


class V25Tests(unittest.TestCase):
    def test_unchanged_30_games_model_vs_elo_and_no_forward_accuracy_claim(self):
        report=run([row(i,i<19) for i in range(30)])
        self.assertEqual(report["games"],30)
        self.assertEqual(report["predictions"]["original"]["correct_winners"],19)
        self.assertEqual(report["predictions"]["elo"]["correct_winners"],30)
        self.assertEqual(report["predictions"]["v23_fixed_blend"]["correct_winners"],19)
        self.assertFalse(report["out_of_sample_accuracy_claim_allowed"])
        self.assertFalse(report["v23_met_numeric_90pct_on_retrospective_games"])
        self.assertEqual(report["weight_precommitted_from_v23"],.5)
        self.assertEqual(len(report["per_game_diagnostics"]),30)

    def test_retrofit_cannot_use_a_different_weight(self):
        a=[row(i,i<19) for i in range(30)]
        report=run(a)
        by_id={r["game_id"]:r for r in report["per_game_diagnostics"]}
        for r in a:
            d=by_id[r["game_id"]]
            self.assertAlmostEqual(d["fixed_blend_home_win"],.5*float(r["home_win_probability"])+.5*float(r["elo_home_win_probability"]),places=5)

    def test_missing_duplicate_future_and_leaky_rows_rejected(self):
        a=[row(i) for i in range(30)]
        with self.assertRaisesRegex(ValueError,"all 30"):
            run(a[:-1])
        a[29]["game_id"]=a[0]["game_id"]
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            run(a)
        a=[row(i) for i in range(30)]
        a[0]["pregame_features_cutoff_exclusive"]="2026-10-13"
        with self.assertRaisesRegex(ValueError,"cutoff"):
            run(a)

    def test_no_saved_joint_probabilities_fabricated_by_candidate(self):
        x=run([row(i) for i in range(30)])
        self.assertNotIn("winner_and_over_4_5_probability",x["predictions"]["v23_fixed_blend"])
        self.assertNotIn("winner_and_over_5_5_probability",x["predictions"]["v23_fixed_blend"])


if __name__ == "__main__":
    unittest.main()
