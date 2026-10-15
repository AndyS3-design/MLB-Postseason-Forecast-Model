"""V24: test time-safe selection and non-interference with production."""
import unittest
import numpy as np
import pandas as pd

from cloud.v24_winner_ablation import CANDIDATES, fit, metrics, validate_and_fit, score_cohorts


def synthetic():
    rng = np.random.default_rng(20241015)
    rows = []
    for year, size in ((2023, 2400), (2024, 2400), (2025, 200), (2026, 90)):
        for i in range(size):
            d = rng.normal()
            p = 1 / (1 + np.exp(-0.25 - .32 * d))
            outcome = int(rng.uniform() < p)
            rows.append({
                "year": year, "date": f"{year}-09-{i%28+1:02d}",
                "game_type": "R" if i % 7 else "P",
                "elo_logit": d,
                "home_elo": 1 / (1 + np.exp(-d)),
                "offense_rpg15_diff": .1 + d + rng.normal(),
                "offense_rpg40_diff": d + rng.normal(),
                "run_allowed_diff": d / 2 + rng.normal(),
                "rest_diff": float(i % 3) - 1,
                "bullpen_used3_diff": rng.normal(),
                "bullpen_used7_diff": rng.normal(),
                "y_home": outcome,
            })
    # Need >2000 regular games in 2023 and 2024.
    return pd.DataFrame(rows)


class V24Tests(unittest.TestCase):
    def test_metrics_exact_and_reject_invalid(self):
        result = metrics([1, 0], [.8, .3])
        self.assertEqual(result["correct"], 2)
        self.assertAlmostEqual(result["brier"], .065)
        for values in ([float("nan")], [float("inf")], [-.1], [1.1]):
            with self.assertRaises(ValueError):
                metrics([1], values)

    def test_no_targets_or_same_day_ids_accepted_as_predictors(self):
        training = synthetic()
        for col in ("y_home", "date", "year", "game_id"):
            with self.subTest(col=col):
                with self.assertRaises(ValueError):
                    fit(training, ("elo_logit", col), .03)
        self.assertFalse(any("sp_" in c or "starter" in c for cols in CANDIDATES.values() for c in cols))

    def test_2025_2026_outcomes_never_select_model_or_hyperparameters(self):
        frame = synthetic()
        baseline, fit_before = validate_and_fit(frame)
        reversed_future = frame.copy()
        reversed_future.loc[reversed_future.year>=2025, "y_home"] = (
            1 - reversed_future.loc[reversed_future.year>=2025, "y_home"])
        identical, fit_after = validate_and_fit(reversed_future)
        self.assertEqual(baseline["winning_candidate"], identical["winning_candidate"])
        self.assertEqual(baseline["selected"], identical["selected"])
        self.assertFalse(baseline["selection_uses_2025_or_2026_results"])
        self.assertEqual(baseline["train_years"], [2023,2024])
        # The fixed future model cannot change when future game results change.
        v = frame.iloc[:8]
        if fit_before is not None:
            cols = baseline["winning_candidate"]["features"]
            np.testing.assert_allclose(
                fit_before.predict_proba(v[cols]), fit_after.predict_proba(v[cols]))

    def test_report_both_baselines_on_exactly_same_test_games(self):
        frame = synthetic()
        chosen, model = validate_and_fit(frame)
        scored = score_cohorts(frame, chosen, model)
        for s in scored.values():
            self.assertEqual(s["n"], s["elo"]["n"])
            self.assertEqual(s["n"], s["selected_candidate"]["n"])
            self.assertEqual(s["status"], "retrospective_diagnostic_not_live_forward_accuracy")


if __name__ == "__main__":
    unittest.main()
