"""Postseason-scoring adjustment: temporal, arithmetic and schema guards."""
import csv,tempfile,unittest
from datetime import date
from pathlib import Path
from v63_postseason import (COLS,load_years,historical_ratio,context_for_game,
                            with_context_rates,retrospective_season_diagnostics)

class PostseasonContextTests(unittest.TestCase):
    def test_user_table_columns_and_seasons(self):
        rows=load_years()
        self.assertEqual([r['Year'] for r in rows],[2022,2023,2024,2025,2026])
        self.assertEqual(len(COLS),11)
        self.assertEqual(rows[-1]['Post_Runs_Per_Game'],3.46)
        self.assertEqual(rows[-1]['Post_Avg_Fastball_MPH'],96.1)
    def test_regular_games_no_overlay(self):
        for day in ('2025-10-17','2026-10-13'):
            x=context_for_game(day,'R')
            self.assertFalse(x['active']);self.assertEqual(x['factor'],1)
    def test_2026_snapshot_cannot_leak_into_earlier_days(self):
        for day in ('2026-09-30','2026-10-10','2026-10-11'):
            r=context_for_game(day,'P')
            self.assertFalse(r['current_2026_snapshot_used'])
            self.assertEqual(r['completed_years_used'],[2022,2023,2024,2025])
        r=context_for_game('2026-10-12','P')
        self.assertTrue(r['current_2026_snapshot_used'])
        self.assertLess(r['factor'],context_for_game('2026-10-11','P')['factor'])
    def test_2025_replay_sees_only_prior_seasons(self):
        r=context_for_game('2025-10-13','P')
        self.assertEqual(r['completed_years_used'],[2022,2023,2024])
        self.assertFalse(r['current_2026_snapshot_used'])
    def test_2024_sees_only_2022_and_2023(self):
        r=context_for_game('2024-10-01','P')
        self.assertEqual(r['completed_years_used'],[2022,2023])
    def test_partial_2026_never_becomes_full_2027_prior(self):
        r=context_for_game('2027-10-17','P')
        self.assertNotIn(2026,r['completed_years_used'])
        self.assertEqual(r['completed_years_used'],[2022,2023,2024,2025])
    def test_opt_out_current_snapshot(self):
        a=context_for_game('2026-10-13','P',include_2026_snapshot=False)
        self.assertFalse(a['current_2026_snapshot_used'])
        self.assertEqual(a['blend_2026_weight'],0)
    def test_per_team_game_rates_not_combined(self):
        rows=load_years()
        self.assertAlmostEqual(historical_ratio(rows[:-1]),
            (3.66+4.10+4.21+4.01)/(4.28+4.62+4.39+4.45))
    def test_rate_multiplier_consistent_on_two_teams(self):
        c=context_for_game('2026-10-13','P')
        h,a=with_context_rates(4.0,4.15,c)
        self.assertAlmostEqual(h+a,8.15*c['factor'])
        self.assertLess(h+a,8.15)
    def test_other_columns_are_diagnostic_not_independent_multipliers(self):
        c=context_for_game('2026-10-13','P')
        self.assertGreater(c['post_reliever_share'],.5)
        self.assertLess(c['post_home_run_rate_ratio'],1)
        self.assertGreater(c['post_fastball_velocity_increase_mph'],0)
        self.assertEqual(c['run_multiplier'],c['factor'])
    def test_no_data_for_2022_replay(self):
        c=context_for_game('2022-10-10','P')
        self.assertFalse(c['active'])
    def test_annual_retrospective_records_count(self):
        z=retrospective_season_diagnostics()
        self.assertEqual([r['year'] for r in z],[2023,2024,2025,2026])
    def test_wrong_schema_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bad.csv';path.write_text('year,runs\n2025,4.5\n')
            with self.assertRaises(ValueError):load_years(path)
    def test_zero_or_negative_data_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bad.csv'
            with path.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=COLS);w.writeheader()
                bad=load_years()[:]
                bad[0]['Post_Runs_Per_Game']=0
                w.writerows(bad)
            with self.assertRaises(ValueError):load_years(path)

if __name__=='__main__':unittest.main()
