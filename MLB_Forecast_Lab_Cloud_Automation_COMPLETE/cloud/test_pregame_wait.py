"""Regression tests for the GitHub Actions pregame watchdog."""
import unittest
from datetime import datetime, timedelta, timezone
from cloud import preflight
from cloud.pregame_wait import await_window

UTC = timezone.utc


class Clock:
    def __init__(self, start):
        self.now = start
        self.sleeps = []
    def clock(self):
        return self.now
    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)


class AwaitPregameTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
        self.clock = Clock(self.start)
        self.game_start = self.start + timedelta(hours=3)
        self.status = 'Pre-Game'

    def fetch(self, day):
        return {'dates': [{'date': '2026-10-15', 'games': [{
            'gamePk': 849818, 'gameType': 'L', 'officialDate': '2026-10-15',
            'gameDate': self.game_start.isoformat(),
            'status': {'detailedState': self.status}
        }]}]} if str(day) == '2026-10-15' else {'dates': []}

    def wait(self):
        return await_window(['849818'], fetcher=self.fetch,
                            clock=self.clock.clock, sleeper=self.clock.sleep)

    def test_three_hour_early_gate_waits_into_safe_original_window(self):
        self.assertEqual(self.wait(), '849818')
        lead = (self.game_start - self.clock.now).total_seconds()/60
        self.assertGreaterEqual(lead, 8)
        self.assertLessEqual(lead, 30)
        self.assertGreater(len(self.clock.sleeps), 1)

    def test_existing_window_does_not_sleep(self):
        self.clock.now = self.game_start - timedelta(minutes=24)
        self.assertEqual(self.wait(), '849818')
        self.assertEqual(self.clock.sleeps, [])

    def test_started_or_postponed_game_is_not_forecast(self):
        self.status = 'In Progress'
        with self.assertRaisesRegex(RuntimeError, 'status'):
            self.wait()

    def test_late_invocation_is_rejected(self):
        self.clock.now = self.game_start - timedelta(minutes=6)
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            self.wait()

    def test_revised_first_pitch_is_rechecked(self):
        def delaying_sleep(seconds):
            self.clock.sleep(seconds)
            if len(self.clock.sleeps) == 1:
                self.game_start += timedelta(minutes=30)
        self.assertEqual(await_window(['849818'], fetcher=self.fetch,
                         clock=self.clock.clock, sleeper=delaying_sleep), '849818')
        self.assertGreaterEqual((self.game_start - self.clock.now).total_seconds()/60, 8)

    def test_unknown_game_and_bound_are_failures_not_false_successes(self):
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            await_window(['888888'], fetcher=self.fetch,
                         clock=self.clock.clock, sleeper=self.clock.sleep)
        with self.assertRaises(TimeoutError):
            await_window(['849818'], fetcher=self.fetch,
                         clock=self.clock.clock, sleeper=self.clock.sleep,
                         max_wait_minutes=20)

    def test_wider_preflight_catches_game_hours_before_first_pitch(self):
        self.assertGreater(preflight.MAX_LEAD_MINUTES, 180)
        matches = preflight.find_approaching_games(self.clock.now, self.fetch)
        self.assertEqual([game['id'] for game in matches], ['849818'])


if __name__ == '__main__':
    unittest.main()
