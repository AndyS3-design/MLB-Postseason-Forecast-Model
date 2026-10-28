"""Deterministic, no-network V30 prospective-denominator regression tests."""
import unittest

from cloud.v30_official_cohort import (
    official_games, historical, grade, validate, metrics, paired_winner_test,
)

def official(gid=849802, home=5, away=4, complete=True):
    teams = {"home": {"team": {"id": 158, "name": "Milwaukee Brewers"}},
             "away": {"team": {"id": 139, "name": "Tampa Bay Rays"}}}
    if complete:
        teams["home"]["score"] = home
        teams["away"]["score"] = away
    return {"gamePk": gid, "gameType": "W", "officialDate": "2026-10-24",
            "gameDate": "2026-10-25T00:00:00Z",
            "status": {"abstractGameState": "Final"}, "teams": teams}

def record():
    m, e = .541, .596
    return {"game_id": "849802", "date": "2026-10-24",
            "forecast_kind": "original_pregame", "home": "MIL", "away": "TBA",
            "home_name": "Milwaukee Brewers", "away_name": "Tampa Bay Rays",
            "forecast_created_utc": "2026-10-24T23:31:13Z",
            "game_start_utc": "2026-10-25T00:00:00Z",
            "predicted_home_win": m, "elo_home_win": e,
            "research_winner_ensemble": {
                "method": "v23_fixed_50_model_50_elo",
                "model_weight": .5, "elo_weight": .5,
                "home_win_probability": (m + e) / 2},
            "expected_runs": {"total": 7.0},
            "total_distribution": {"4": .25, "9": .75},
            "win_and_over_probabilities": {
                "4.5": {"home_win_and_over": .40, "away_win_and_over": .35,
                        "favorite_win_and_over": .40, "favorite_side": "home", "over": .75},
                "5.5": {"home_win_and_over": .40, "away_win_and_over": .35,
                        "favorite_win_and_over": .40, "favorite_side": "home", "over": .75}}}

def fixture_games():
    return official_games({"dates": [{"date": "2026-10-24", "games": [official()]}]},
                          __import__("datetime").date(2026, 10, 25),
                          lambda _: None)

BASE = {"n": 261, "mean": 8.241, "over": {"4.5": .7893, "5.5": .705}}

class V30Tests(unittest.TestCase):
    def test_official_complete_and_no_duplicate(self):
        self.assertEqual(len(fixture_games()), 1)
        data = {"dates": [{"date": "2026-10-24", "games": [official(), official()]}]}
        self.assertEqual(len(official_games(data, __import__("datetime").date(2026, 10, 25),
                                            lambda _: None)), 1)

    def test_conflicting_official_finals_rejected(self):
        data = {"dates": [{"date": "2026-10-24",
                           "games": [official(), official(home=6)]}]}
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            official_games(data, __import__("datetime").date(2026, 10, 25), lambda _: None)

    def test_scoreless_final_recovered_from_official_feed(self):
        feed = {"gameData": {"game": {"pk": 849802},
                             "status": {"abstractGameState": "Final"},
                             "datetime": {"officialDate": "2026-10-24"},
                             "teams": {"home": {"id": 158}, "away": {"id": 139}}},
                "liveData": {"linescore": {"teams": {"home": {"runs": 5},
                                                     "away": {"runs": 4}}}}}
        data = {"dates": [{"date": "2026-10-24", "games": [official(complete=False)]}]}
        games = official_games(data, __import__("datetime").date(2026, 10, 25),
                               lambda _: feed)
        self.assertEqual((games[0]["home"], games[0]["away"]), (5, 4))
        self.assertNotIn("score", data["dates"][0]["games"][0]["teams"]["home"])

    def test_scoreless_final_wrong_feed_fails_closed(self):
        data = {"dates": [{"date": "2026-10-24", "games": [official(complete=False)]}]}
        with self.assertRaises((KeyError, ValueError)):
            official_games(data, __import__("datetime").date(2026, 10, 25),
                           lambda _: {"gameData": {"game": {"pk": 999}}})

    def test_official_team_name_must_be_present(self):
        from datetime import date
        bad = official()
        del bad["teams"]["home"]["team"]["name"]
        with self.assertRaisesRegex(ValueError, "Official team identity unavailable"):
            official_games({"dates": [{"date": "2026-10-24", "games": [bad]}]},
                           date(2026, 10, 25), lambda _: None)

    def test_conflicting_official_team_identity_duplicate_rejected(self):
        from datetime import date
        changed = official()
        changed["teams"]["away"]["team"]["name"] = "Cleveland Guardians"
        with self.assertRaisesRegex(ValueError, "Conflicting official final"):
            official_games({"dates": [{"date": "2026-10-24",
                                       "games": [official(), changed]}]},
                           date(2026, 10, 25), lambda _: None)

    def test_swapped_forecast_team_names_invalid_not_excluded(self):
        from datetime import date
        bad = record()
        bad["home_name"], bad["away_name"] = bad["away_name"], bad["home_name"]
        result = grade(fixture_games(), {"849802": bad}, BASE,
                       as_of=date(2026, 10, 25), verifier=lambda *_: None)
        self.assertEqual(result["official_completed_games"], 1)
        self.assertEqual(result["valid_frozen_originals"], 0)
        self.assertEqual(result["correct_full_cohort"], 0)
        self.assertEqual(result["matched_winners"]["original"]["n"], 0)
        self.assertIn("team identity", result["invalid_originals"][0]["reason"])

    def test_missing_forecast_team_name_invalid(self):
        from datetime import date
        bad = record()
        bad.pop("home_name")
        result = grade(fixture_games(), {"849802": bad}, BASE,
                       as_of=date(2026, 10, 25), verifier=lambda *_: None)
        self.assertEqual(result["correct_full_cohort"], 0)
        self.assertEqual(result["valid_frozen_originals"], 0)

    def test_missing_forecast_remains_in_denominator(self):
        game = fixture_games()[0]
        extra = dict(game, game_id="999999")
        result = grade([game, extra], {"849802": record()}, BASE,
                       as_of=__import__("datetime").date(2026, 10, 25),
                       verifier=lambda r, n: None)
        self.assertEqual((result["correct_full_cohort"],
                          result["official_completed_games"]), (1, 2))
        self.assertEqual(result["matched_winners"]["original"]["n"], 1)
        self.assertEqual(result["missing_ids"], ["999999"])

    def test_first_commit_verifier_required(self):
        def deny(r, name):
            raise ValueError("first commit is late")
        result = grade(fixture_games(), {"849802": record()}, BASE,
                       as_of=__import__("datetime").date(2026, 10, 25),
                       verifier=deny)
        self.assertEqual(result["valid_frozen_originals"], 0)
        self.assertEqual(result["correct_full_cohort"], 0)

    def test_v23_cannot_be_refitted_after_outcome(self):
        r = record()
        r["research_winner_ensemble"]["home_win_probability"] = .99
        with self.assertRaisesRegex(ValueError, "Invalid frozen V23"):
            validate(r, fixture_games()[0], verifier=lambda *_: None)

    def test_late_original_invalid(self):
        r = record()
        r["forecast_created_utc"] = "2026-10-25T00:00:01Z"
        with self.assertRaisesRegex(ValueError, "pre-first-pitch"):
            validate(r, fixture_games()[0], verifier=lambda *_: None)

    def test_genuine_joint_only_no_marginal_product(self):
        r = record()
        r["win_and_over_probabilities"]["4.5"]["favorite_win_and_over"] = .99
        result = grade(fixture_games(), {"849802": r}, BASE,
                       as_of=__import__("datetime").date(2026, 10, 25),
                       verifier=lambda *_: None)
        self.assertEqual(result["same_simulation_joint"]["4.5"]["n"], 0)
        self.assertEqual(result["same_simulation_joint"]["5.5"]["n"], 1)
        self.assertEqual(result["over"]["4.5"]["original"]["n"], 1)

    def test_joint_event_count_not_confused_with_threshold_accuracy(self):
        result = grade(fixture_games(), {"849802": record()}, BASE,
                       as_of=__import__("datetime").date(2026, 10, 25),
                       verifier=lambda *_: None)
        joint = result["same_simulation_joint"]["4.5"]
        self.assertEqual(joint["events_occurred"], 1)
        self.assertEqual(joint["correct"], 0)
        self.assertTrue(joint["correct_is_threshold_classification_not_event_count"])

    def test_as_of_is_exclusive_and_never_grades_today(self):
        from datetime import date
        fixture = {"dates": [{"date": "2026-10-24", "games": [official()]}]}
        self.assertEqual(official_games(fixture, date(2026, 10, 24), lambda _: None), [])
        self.assertEqual(len(official_games(fixture, date(2026, 10, 25),
                                            lambda _: None)), 1)

    def test_90pct_gate_requires_thirty_full_cohort_games(self):
        from datetime import date
        games, records = [], {}
        for i in range(30):
            gid = str(850000 + i)
            g = dict(fixture_games()[0], game_id=gid,
                     home=5 if i < 27 else 3, away=4)
            r = record()
            r["game_id"] = gid
            games.append(g)
            records[gid] = r
        grade30 = grade(games, records, BASE, as_of=date(2026, 10, 25),
                        verifier=lambda *_: None)
        self.assertEqual(grade30["official_completed_games"], 30)
        self.assertEqual(grade30["correct_full_cohort"], 27)
        self.assertTrue(grade30["prospective_90pct_verified"])
        self.assertEqual(grade30["prospective_90pct_minimum_games"], 30)
        grade29 = grade(games[:29], records, BASE, as_of=date(2026, 10, 25),
                        verifier=lambda *_: None)
        self.assertEqual(grade29["correct_full_cohort"], 27)
        self.assertFalse(grade29["prospective_90pct_verified"])
        records.pop(games[0]["game_id"])
        missing = grade(games, records, BASE, as_of=date(2026, 10, 25),
                        verifier=lambda *_: None)
        self.assertEqual(missing["correct_full_cohort"], 26)
        self.assertEqual(len(missing["missing_ids"]), 1)
        self.assertFalse(missing["prospective_90pct_verified"])

    def test_historical_baseline_rejects_2026(self):
        rows = [{"year": str(y), "game_id": str(y), "home_runs": "5",
                 "away_runs": "4", "total_runs": "9"} for y in range(2020, 2027)]
        with self.assertRaisesRegex(ValueError, "year/ID"):
            historical(rows)
        self.assertEqual(historical(rows[:-1])["n"], 6)

    def test_exact_mcnemar_small_discordant_sample(self):
        first = [(.6, 1), (.4, 0)]
        second = [(.4, 1), (.6, 0)]
        result = paired_winner_test(first, second)
        self.assertEqual(result["n_matched"], 2)
        self.assertEqual(result["first_only_correct"], 2)
        self.assertEqual(result["second_only_correct"], 0)
        self.assertEqual(result["discordant"], 2)
        self.assertEqual(result["exact_two_sided_p"], 0.5)

    def test_exact_mcnemar_ten_unopposed_disagreements(self):
        result = paired_winner_test([(.6, 1)] * 10, [(.4, 1)] * 10)
        self.assertAlmostEqual(result["exact_two_sided_p"], .001953125)

    def test_exact_mcnemar_no_disagreement_and_identity_guards(self):
        self.assertEqual(paired_winner_test([(.6, 1)], [(.8, 1)])
                         ["exact_two_sided_p"], 1.0)
        with self.assertRaisesRegex(ValueError, "sample sizes"):
            paired_winner_test([(.6, 1)], [])
        with self.assertRaisesRegex(ValueError, "outcomes differ"):
            paired_winner_test([(.6, 1)], [(.6, 0)])

    def test_scorecard_reports_exact_paired_comparisons(self):
        result = grade(fixture_games(), {"849802": record()}, BASE,
                       as_of=__import__("datetime").date(2026, 10, 25),
                       verifier=lambda *_: None)
        tests = result["paired_winner_tests"]
        self.assertEqual(set(tests), {"original_vs_elo", "original_vs_v23",
                                      "elo_vs_v23"})
        self.assertEqual(tests["original_vs_elo"]["n_matched"], 1)
        self.assertEqual(tests["original_vs_elo"]["exact_two_sided_p"], 1.0)

    def test_probabilistic_brier_on_same_game(self):
        result = grade(fixture_games(), {"849802": record()}, BASE,
                       as_of=__import__("datetime").date(2026, 10, 25),
                       verifier=lambda *_: None)
        self.assertEqual(result["matched_winners"]["original"]["n"], 1)
        self.assertEqual(result["matched_winners"]["elo"]["n"], 1)
        self.assertEqual(result["matched_winners"]["v23"]["n"], 1)
        self.assertAlmostEqual(result["matched_winners"]["original"]["brier"],
                               (1 - .541) ** 2, places=6)

if __name__ == "__main__":
    unittest.main()
