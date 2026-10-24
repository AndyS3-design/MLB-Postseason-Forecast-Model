"""Deterministic tests: first GitHub commit, not a backdated JSON timestamp."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from cloud.v28_first_commit_provenance import audit, verify_one


def original(gid="849805"):
    return {
        "game_id": gid, "date": "2026-10-23", "forecast_kind": "original_pregame",
        "forecast_created_utc": "2026-10-23T23:31:19Z",
        "game_start_utc": "2026-10-24T00:00:00Z",
        "home": "MIL", "away": "TBA",
        "predicted_home_win": .6129, "elo_home_win": .5875,
        "win_and_over_probabilities": {
            "4.5": {"favorite_win_and_over": .5055, "method": "same simulation"}},
    }


def github(first, when="2026-10-23T23:31:45Z", *, history=True):
    def get(endpoint):
        if "/commits?" in endpoint:
            if not history:
                return []
            return [{"sha": "a" * 40, "commit": {"committer": {"date": when}}}]
        if "/contents/" in endpoint and "?ref=" in endpoint:
            blob = base64.b64encode(json.dumps(first).encode()).decode()
            return {"encoding": "base64", "content": blob}
        raise AssertionError("Unexpected GitHub API request: " + endpoint)
    return get


class FirstCommitTests(unittest.TestCase):
    def test_first_commit_before_first_pitch(self):
        row = verify_one(original(), "849805.json", "owner/repo", github(original()))
        self.assertTrue(row["valid"])
        self.assertEqual(row["game_id"], "849805")

    def test_append_only_official_settlement_is_legal(self):
        now = original()
        now["official_final"] = {"home": 3, "away": 2}
        now["evaluation"] = {"correct_winner": True}
        self.assertTrue(verify_one(now, "849805.json", "owner/repo",
                                   github(original()))["valid"])

    def test_first_commit_after_pitch_is_not_prospective(self):
        with self.assertRaisesRegex(ValueError, "not within pre-first-pitch"):
            verify_one(original(), "849805.json", "owner/repo",
                       github(original(), "2026-10-24T00:01:00Z"))

    def test_first_commit_before_claimed_creation_is_invalid(self):
        with self.assertRaisesRegex(ValueError, "not within pre-first-pitch"):
            verify_one(original(), "849805.json", "owner/repo",
                       github(original(), "2026-10-23T23:20:00Z"))

    def test_rewritten_frozen_probabilities_or_joint_odds_fail(self):
        for key in ("predicted_home_win", "win_and_over_probabilities",
                    "forecast_created_utc", "game_start_utc"):
            now = deepcopy(original())
            if key == "predicted_home_win":
                now[key] = .9
            elif key == "win_and_over_probabilities":
                now[key]["4.5"]["favorite_win_and_over"] = .99
            elif key == "forecast_created_utc":
                now[key] = "2026-10-23T23:32:00Z"
            else:
                now[key] = "2026-10-24T01:00:00Z"
            with self.subTest(field=key):
                with self.assertRaisesRegex(ValueError, "Immutable original differs"):
                    verify_one(now, "849805.json", "owner/repo", github(original()))

    def test_first_commit_must_be_unsettled(self):
        first = original()
        first["official_final"] = {"home": 3, "away": 2}
        with self.assertRaisesRegex(ValueError, "already settled"):
            verify_one(original(), "849805.json", "owner/repo", github(first))

    def test_missing_first_commit_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "No GitHub first commit"):
            verify_one(original(), "849805.json", "owner/repo",
                       github(original(), history=False))

    def test_audit_skips_only_predeclared_pretracking_date(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            eligible = original()
            (folder / "849805.json").write_text(json.dumps(eligible))
            older = original("849813")
            older["date"] = "2026-10-13"
            (folder / "849813.json").write_text(json.dumps(older))
            result = audit(folder, "owner/repo", github(eligible))
            self.assertEqual(result["eligible_originals"], 1)
            self.assertEqual(result["verified_originals"], 1)
            self.assertEqual(result["pretracking_original_ids"], ["849813"])

    def test_invalid_record_remains_in_denominator_of_saved_records(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "849805.json").write_text(json.dumps(original()))
            bad = original("849999")
            bad["forecast_created_utc"] = "2026-10-24T01:00:00Z"
            (folder / "849999.json").write_text(json.dumps(bad))
            result = audit(folder, "owner/repo", github(original()))
            self.assertEqual(result["eligible_originals"], 2)
            self.assertEqual(result["verified_originals"], 1)
            self.assertEqual(len(result["failed_originals"]), 1)
            self.assertFalse(result["all_saved_originals_verified"])


if __name__ == "__main__":
    unittest.main()
