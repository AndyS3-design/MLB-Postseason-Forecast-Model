"""V10 independent MLB schedule denominator: no network or real fixtures required."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from cloud.v10_schedule_audit import reconcile


def game(game_id, day="2026-10-14", state="Final", home=4, away=2):
    return {"gamePk": game_id, "officialDate": day, "gameType": "L",
            "status": {"abstractGameState": state},
            "teams": {"home": {"score": home}, "away": {"score": away}}}


def original(game_id, day="2026-10-14", created="2026-10-14T19:40:00+00:00"):
    return {"game_id": str(game_id), "date": day,
            "forecast_kind": "original_pregame",
            "game_start_utc": "2026-10-14T20:00:00+00:00",
            "forecast_created_utc": created}


class ScheduleAuditTests(unittest.TestCase):
    def write_original(self, path, obj):
        dest = Path(path) / "cloud_records" / "predictions"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / (str(obj["game_id"]) + ".json")).write_text(json.dumps(obj))

    def payload(self, *items):
        return {"dates": [{"date": "2026-10-14", "games": list(items)}]}

    def test_unimported_game_still_counts_as_missed_original(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_original(d, original(101))
            finished = [game(101), game(102)]
            with patch("cloud.v10_schedule_audit.all_finals", return_value={}):
                r = reconcile(d, date(2026, 10, 15),
                              fetcher=lambda url: self.payload(*finished))
            self.assertEqual(r["official_completed_games"], 2)
            self.assertEqual(r["completed_games_imported"], 0)
            self.assertEqual(r["missing_import_count"], 2)
            self.assertEqual(r["missing_original_count"], 1)
            self.assertEqual(r["official_capture_fraction"], 0.5)
            self.assertEqual(r["status"], "needs_attention")

    def test_doubleheaders_and_status_filters(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_original(d, original(1))
            self.write_original(d, original(2))
            recorded = {
                str(i): {"game_id": str(i), "date": "2026-10-14",
                         "home_final": "4", "away_final": "2"}
                for i in (1, 2)
            }
            with patch("cloud.v10_schedule_audit.all_finals", return_value=recorded):
                r = reconcile(d, "2026-10-15", fetcher=lambda url: self.payload(
                    game(1), game(2), game(3, state="Postponed"),
                    game(4, day="2026-10-15"), game(5, day="2026-10-13")))
            self.assertEqual(r["official_completed_games"], 2)
            self.assertEqual(r["completed_games_imported"], 2)
            self.assertEqual(r["official_games_with_valid_original"], 2)
            self.assertEqual(r["status"], "reconciled")

    def test_late_original_and_wrong_local_score(self):
        with tempfile.TemporaryDirectory() as d:
            self.write_original(d, original(1, created="2026-10-14T20:01:00+00:00"))
            wrong = {"1": {"game_id": "1", "date": "2026-10-14",
                           "home_final": "5", "away_final": "2"}}
            with patch("cloud.v10_schedule_audit.all_finals", return_value=wrong):
                r = reconcile(d, "2026-10-15", fetcher=lambda url: self.payload(game(1)))
            self.assertEqual(r["invalid_original_count"], 1)
            self.assertEqual(r["score_conflict_count"], 1)
            self.assertEqual(r["import_coverage_fraction"], 0)

    def test_no_false_100_percent_before_launch_or_on_off_day(self):
        with tempfile.TemporaryDirectory() as d:
            no_start = reconcile(d, "2026-10-14", fetcher=lambda url: self.fail("must not fetch"))
            self.assertEqual(no_start["status"], "not_started")
            self.assertIsNone(no_start["official_capture_fraction"])
            with patch("cloud.v10_schedule_audit.all_finals", return_value={}):
                off_day = reconcile(d, "2026-10-15", fetcher=lambda url: self.payload())
            self.assertIsNone(off_day["official_capture_fraction"])
            self.assertEqual(off_day["status"], "no_official_finals_in_window")

    def test_malformed_response_and_missing_score_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                reconcile(d, "2026-10-15", fetcher=lambda url: {})
            bad = game(5)
            del bad["teams"]["home"]["score"]
            with patch("cloud.v10_schedule_audit.all_finals", return_value={}):
                r = reconcile(d, "2026-10-15", fetcher=lambda url: self.payload(bad))
            self.assertEqual(r["official_finals_missing_scores_count"], 1)
            self.assertIsNone(r["official_capture_fraction"])
            self.assertEqual(r["status"], "needs_attention")

    def test_full_window_uses_strict_prior_et_dates(self):
        with tempfile.TemporaryDirectory() as d:
            def mock(url):
                self.assertIn("startDate=2026-10-14", url)
                self.assertIn("endDate=2026-10-15", url)
                return self.payload()
            with patch("cloud.v10_schedule_audit.all_finals", return_value={}):
                reconcile(d, "2026-10-16", fetcher=mock)


if __name__ == "__main__":
    unittest.main()
