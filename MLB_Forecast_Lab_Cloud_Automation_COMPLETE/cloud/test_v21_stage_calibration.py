"""V21 stage priors must never use 2026 or the season being forecast."""
import csv,tempfile,unittest
from pathlib import Path
from cloud.v21_stage_calibration import (
    ROOT,load_history,history_factor,evaluate_league_history,
    evaluate_v20_backtest,run,WEIGHTS
)

class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=load_history()

    def test_complete_official_history(self):
        self.assertEqual(len(self.rows),261)
        self.assertEqual(len({x['game_id'] for x in self.rows}),261)

    def test_2026_cannot_influence_history_factors(self):
        sample=history_factor(self.rows,2026,'D',.25)
        contaminated=self.rows+[{'year':2026,'stage':'D','total':10000,'game_id':'fake'}]
        self.assertEqual(sample,history_factor(contaminated,2026,'D',.25))
        self.assertEqual(history_factor(self.rows,2026,'D',0),1)
        for stage in ('F','D','L','W'):
            with self.subTest(stage=stage):
                self.assertGreater(history_factor(self.rows,2026,stage,.25),0)
        with self.assertRaises(ValueError):
            history_factor(self.rows,2026,'X',.25)
        with self.assertRaises(ValueError):
            history_factor(self.rows,2026,'D',1.1)

    def test_after_early_selection_holdout_is_not_selection(self):
        report=run()
        selected=report['selected_weight_early_2021_2022_only']
        self.assertIn(selected,WEIGHTS)
        self.assertEqual(report['archive_games'],261)
        self.assertEqual(report['early_year_results'][str(selected)]['n'],77)
        self.assertEqual(report['later_year_results_not_used_for_selection'][str(selected)]['n'],131)
        self.assertFalse(report['2026_used_for_selection'])
        self.assertNotIn('retrospective_v20_2026_mean_only_sensitivity',report)

    def test_historical_round_count_integrity(self):
        early=evaluate_league_history(self.rows,(2021,2022),.25)
        late=evaluate_league_history(self.rows,(2023,2024,2025),.25)
        self.assertEqual(sum(x['n'] for x in early['by_round'].values()),77)
        self.assertEqual(sum(x['n'] for x in late['by_round'].values()),131)

    def test_no_shortened_or_mixed_2026_replay_evaluation(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'replay.csv'
            p.write_text('date,game_id,round_code,model_version,expected_total_runs,actual_total_runs\n'
                         '2026-10-01,849844,F,18.0.0-forecast-integrity,8.5,8\n')
            with self.assertRaisesRegex(ValueError,'30'):
                evaluate_v20_backtest(p,self.rows,.25)
            p.write_text('date,game_id,round_code,model_version,expected_total_runs,actual_total_runs\n'
                         '2025-10-01,849844,F,18.0.0-forecast-integrity,8.5,8\n')
            with self.assertRaisesRegex(ValueError,'Mixed year'):
                evaluate_v20_backtest(p,self.rows,.25)

if __name__=='__main__':unittest.main()
