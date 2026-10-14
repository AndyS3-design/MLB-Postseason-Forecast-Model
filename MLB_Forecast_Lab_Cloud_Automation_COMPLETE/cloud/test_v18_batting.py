"""Offline regressions for completed-game batting ingestion and feature cutoffs."""
import copy
import csv
from datetime import date
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from extended_eval import all_games
from ingest_mlb import COLUMNS
from matchup_model import Team
from v4_batting import (BATTING_FIELDS, add_team_batting, batting_history_report,
                        complete_batting, recent_batting_coverage)
from v4_matchup_core import FEATURES, historical_team_rows, pregame_rows
from v4_workflow import build_assets, generate


def game(gid='101', day='2026-07-01', home='NYA', away='BOS'):
    return dict(game_id='api-' + gid, game_num=gid, date=pd.Timestamp(day),
                year=int(day[:4]), home=home, away=away, game_type='R',
                home_final=10, away_final=2, home_reg=10, away_reg=2,
                home_sp='', away_sp='')


def batting(ab=40, hits=20, hr=3):
    return dict(atBats=ab, hits=hits, baseOnBalls=0, hitByPitch=0,
                sacFlies=0, doubles=0, triples=0, homeRuns=hr)


def boxscore(home=None, away=None):
    return {'teams': {
        'home': {'team': {'id': 147}, 'teamStats': {'batting': {
            'runs': 10, **(home if home is not None else batting())}}},
        'away': {'team': {'id': 111}, 'teamStats': {'batting': {
            'runs': 2, **(away if away is not None else batting(35, 5, 0))}}},
    }}


def with_totals(observation, side='home', totals=None):
    observation = observation.copy()
    for key, api_field in BATTING_FIELDS.items():
        observation[side + '_' + key] = (totals or batting())[api_field]
    return observation


class BattingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name) / 'data'
        (self.data / 'mlb_boxscores').mkdir(parents=True)

    def cache(self, gid='101', payload=None):
        (self.data / 'mlb_boxscores' / (gid + '.json')).write_text(
            json.dumps(boxscore() if payload is None else payload), encoding='utf-8')

    def test_real_csv_ingestion_restores_next_date_obp_and_iso(self):
        row = dict(game_id='101', date='2026-07-01', first_pitch_utc='2026-07-01T23:00:00Z',
                   year=2026, game_type='R', home='NYA', away='BOS',
                   home_final=10, away_final=2, home_reg=10, away_reg=2,
                   home_sp='', away_sp='', source='MLB Stats API')
        with (self.data / 'mlb_2026_regular.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerow(row)
        self.cache()
        with patch('extended_eval.read_rows', return_value=[]):
            ingested = all_games(self.data, True)
        self.assertNotIn('home_ab', ingested[0])
        enriched, report = add_team_batting(ingested, self.data)
        self.assertNotIn('home_ab', ingested[0])  # input is immutable
        self.assertEqual(enriched[0]['game_id'], 'api-101')
        self.assertEqual(enriched[0]['game_num'], '101')
        self.assertEqual(report['team_games_available'], 2)
        rows = pregame_rows(enriched, '2026-07-02', 'NYA', 'BOS')
        home = rows[rows.side == 'home'].iloc[0]
        self.assertEqual(home.own_rpg15, 10)
        self.assertAlmostEqual(home.own_obp15, (20 + 80 * .315) / 120)
        self.assertAlmostEqual(home.own_iso15, (9 + 80 * .155) / 120)

    def test_missing_totals_are_explicit_and_do_not_become_observed_zeros(self):
        enriched, report = add_team_batting([game()], self.data)
        self.assertEqual(report['team_games_unavailable'], 2)
        self.assertEqual(enriched[0]['home_batting_status'], 'missing_boxscore')
        self.assertNotIn('home_ab', enriched[0])
        team = Team()
        team.record(date(2026, 7, 1), 10, 2, enriched[0], 'home', '')
        self.assertIsNone(team.history[0]['ab'])
        self.assertIsNone(team.history[0]['hits'])
        signals = team.signals(date(2026, 7, 2), '')
        self.assertEqual(signals['batting_known15'], 0)
        self.assertEqual(signals['batting_missing15'], 1)
        self.assertEqual(signals['obp15'], .315)
        self.assertEqual(signals['iso15'], .155)
        self.assertEqual(signals['rpg15'], 10)

    def test_true_zero_hits_count_as_a_known_observation(self):
        observation = with_totals(game(), totals=batting(27, 0, 0))
        team = Team()
        team.record(date(2026, 7, 1), 0, 2, observation, 'home', '')
        signals = team.signals(date(2026, 7, 2), '')
        self.assertEqual(signals['batting_known15'], 1)
        self.assertEqual(team.history[0]['hits'], 0)
        self.assertAlmostEqual(signals['obp15'], 80 * .315 / 107)

    def test_doubleheaders_use_exact_ids_and_only_later_dates(self):
        self.cache('101', boxscore(batting(30, 1, 0)))
        self.cache('102', boxscore(batting(40, 20, 3)))
        originals = [game('101'), game('102'), game('103', '2026-07-02')]
        enriched, _ = add_team_batting(originals, self.data)
        self.assertEqual([g.get('home_hits') for g in enriched], [1, 20, None])
        frame = historical_team_rows(enriched)
        same_date = frame[(frame.date == '2026-07-01') & (frame.side == 'home')]
        self.assertEqual(list(same_date.game_id), ['api-101', 'api-102'])
        self.assertEqual(list(same_date.own_obp15), [.315, .315])
        later = frame[(frame.date == '2026-07-02') & (frame.side == 'home')].iloc[0]
        self.assertAlmostEqual(later.own_obp15, (21 + 80 * .315) / 150)
        self.assertAlmostEqual(later.own_iso15, (9 + 80 * .155) / 150)

    def test_game_day_and_future_boxscores_cannot_change_forecast_features_or_coverage(self):
        self.cache('101')
        self.cache('102', boxscore(batting(50, 40, 20)))
        self.cache('103', boxscore(batting(50, 45, 30)))
        observations = [game(), game('102', '2026-07-02'), game('103', '2026-07-03')]
        enriched, _ = add_team_batting(observations, self.data)
        before = pregame_rows(enriched[:1], '2026-07-02', 'NYA', 'BOS')
        after = pregame_rows(enriched, '2026-07-02', 'NYA', 'BOS')
        pd.testing.assert_frame_equal(before, after)
        coverage = recent_batting_coverage(enriched, '2026-07-02', 'NYA')
        self.assertEqual(coverage['prior_team_games'], 1)
        self.assertEqual(coverage['known_team_games'], 1)
        self.assertEqual(batting_history_report(enriched, '2026-07-02')['cached_games_matched'], 1)

    def test_preserves_existing_retrosheet_totals_even_with_unusable_cache(self):
        original = with_totals(with_totals(game(), 'away', batting(33, 6, 0)))
        original['game_id'] = 'retro-20260701-BOS-NYA-0'
        original['game_num'] = '0'
        self.cache(payload={'teams': {}})
        enriched, report = add_team_batting([original], self.data)
        for key, value in original.items():
            self.assertEqual(enriched[0][key], value)
        self.assertEqual(report['status_counts'], {'observed_input': 2})

    def test_missing_fields_are_not_imputed_but_other_side_can_be_used(self):
        raw = boxscore()
        del raw['teams']['home']['teamStats']['batting']['hitByPitch']
        self.cache(payload=raw)
        enriched, report = add_team_batting([game()], self.data)
        self.assertNotIn('home_ab', enriched[0])
        self.assertEqual(enriched[0]['home_batting_status'], 'invalid_or_conflicting_batting_totals')
        self.assertEqual(enriched[0]['away_hits'], 5)
        self.assertEqual(report['team_games_available'], 1)
        self.assertEqual(report['team_games_unavailable'], 1)

    def test_rejects_noninteger_negative_and_incoherent_batting(self):
        cases = [('atBats', 0), ('hits', -1), ('hits', 1.5), ('hits', True),
                 ('hits', float('nan')), ('hits', float('inf')), ('hits', 41),
                 ('homeRuns', 21), ('doubles', None)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                raw = boxscore()
                raw['teams']['home']['teamStats']['batting'][field] = value
                self.cache(payload=raw)
                enriched, _ = add_team_batting([game()], self.data)
                self.assertIsNone(complete_batting(enriched[0], 'home'))
                self.assertNotIn('home_ab', enriched[0])
                self.assertEqual(enriched[0]['away_batting_status'], 'verified_cached_boxscore')

    def test_rejects_malformed_cache_and_conflicting_team_score_or_metadata(self):
        variants = [[], {}, {'teams': []}, {**boxscore(), 'status': 'Final'},
                    {**boxscore(), 'status': {'abstractGameState': 'Live'}},
                    {**boxscore(), 'gamePk': 102},
                    {**boxscore(), 'officialDate': '2026-07-02'}]
        wrong_team = boxscore()
        wrong_team['teams']['home']['team']['id'] = 111
        variants.append(wrong_team)
        wrong_score = boxscore()
        wrong_score['teams']['home']['teamStats']['batting']['runs'] = 9
        variants.append(wrong_score)
        for raw in variants:
            with self.subTest(raw=raw):
                self.cache(payload=raw)
                enriched, _ = add_team_batting([game()], self.data)
                self.assertNotIn('home_ab', enriched[0])
                self.assertNotIn('away_ab', enriched[0])
                self.assertEqual(enriched[0]['home_batting_status'], 'invalid_or_conflicting_boxscore')
        (self.data / 'mlb_boxscores' / '101.json').write_text('{invalid')
        enriched, _ = add_team_batting([game()], self.data)
        self.assertEqual(enriched[0]['home_batting_status'], 'invalid_or_conflicting_boxscore')

    def test_partial_existing_totals_must_agree_with_cache(self):
        self.cache()
        original = {**game(), 'home_ab': 41}
        enriched, _ = add_team_batting([original], self.data)
        self.assertEqual(enriched[0]['home_ab'], 41)
        self.assertNotIn('home_hits', enriched[0])
        self.assertEqual(enriched[0]['home_batting_status'], 'invalid_or_conflicting_batting_totals')
        self.assertEqual(enriched[0]['away_batting_status'], 'verified_cached_boxscore')

    def test_conflicting_game_identity_never_reuses_cache(self):
        self.cache()
        originals = [game(), game(day='2026-07-02')]
        enriched, report = add_team_batting(originals, self.data)
        self.assertEqual(report['team_games_available'], 0)
        self.assertTrue(all(g['home_batting_status'] == 'conflicting_game_identity'
                            for g in enriched))
        self.assertTrue(all('home_ab' not in g for g in enriched))

    def test_recent_coverage_matches_last15_and_resets_at_season_boundary(self):
        observations = [with_totals(game(str(100 + i), f'2026-07-{i + 1:02}'))
                        for i in range(17)]
        observations[-1] = game('116', '2026-07-17')
        observations.append(with_totals(game('1', '2025-07-01')))
        coverage = recent_batting_coverage(observations, '2026-07-18', 'NYA')
        self.assertEqual(coverage['prior_team_games'], 15)
        self.assertEqual(coverage['known_team_games'], 14)
        self.assertEqual(coverage['missing_team_games'], 1)
        self.assertEqual(recent_batting_coverage(observations, '2027-01-01', 'NYA')['prior_team_games'], 0)

    def test_build_assets_enriches_current_history_but_keeps_frozen_training_frame(self):
        retrosheet = [with_totals(with_totals(game('1', '2025-07-01'), 'away')),
                      with_totals(with_totals(game('2', '2025-07-02'), 'away'))]
        for observation in retrosheet:
            observation['game_id'] = 'retro-' + observation['game_id']
        self.cache()
        originals = retrosheet + [game()]
        expected = historical_team_rows(copy.deepcopy(retrosheet))
        fit = SimpleNamespace(training_years=[2025], coverage_note='fixture')
        captured = []

        def cache_fit(root, frame):
            captured.append(frame.copy())
            return fit, {'hit': True}

        with patch('v4_workflow.loaded_details', return_value=({}, {}, {})), \
                patch('v4_workflow.load_or_train', side_effect=cache_fit), \
                patch('v4_workflow.park_training_factors', return_value={}):
            assets = build_assets(originals, self.data.parent)
        pd.testing.assert_frame_equal(captured[0], expected)
        self.assertEqual(set(captured[0].year), {2025})
        self.assertEqual(assets['enriched'][-1]['home_hits'], 20)
        self.assertEqual(assets['batting_coverage']['cached_games_matched'], 1)

    def test_forecast_reports_missing_batting_and_strictly_prior_coverage(self):
        self.cache('101')
        self.cache('103')
        originals = [game(), game('102', '2026-07-02'), game('103', '2026-07-03')]
        enriched, report = add_team_batting(originals, self.data)
        fit = SimpleNamespace(features=FEATURES, alpha=1., training_rows=4000,
                              validation_poisson_deviance=1.,
                              pipeline=SimpleNamespace(predict=lambda values: np.repeat(4.5, len(values))))
        assets = dict(enriched=enriched, hands={}, details_n=0, fit=fit,
                      parks={}, fielding_games_matched=0, training_years=[2023, 2024, 2025],
                      batting_coverage=report)
        with patch('v4_workflow.context_for_game', return_value={}), \
                patch('v4_workflow.with_context_rates', side_effect=lambda home, away, context: (home, away)):
            result = generate(originals, self.data.parent, '2026-07-03',
                              {'id': '104', 'home': 'NYA', 'away': 'BOS'}, assets=assets, n=1000)
        coverage = result['provenance']['recent_team_batting']['home']
        self.assertEqual(coverage['prior_team_games'], 2)
        self.assertEqual(coverage['known_team_games'], 1)
        self.assertEqual(coverage['missing_team_games'], 1)
        self.assertEqual(result['provenance']['batting_history']['cached_games_matched'], 1)
        self.assertTrue(any('home rolling batting totals unavailable for 1 of 2' in gap
                            for gap in result['data_gaps']))
        self.assertTrue(any('away rolling batting totals unavailable for 1 of 2' in gap
                            for gap in result['data_gaps']))
        json.dumps(result)  # new provenance remains serializable


if __name__ == '__main__':
    unittest.main()
