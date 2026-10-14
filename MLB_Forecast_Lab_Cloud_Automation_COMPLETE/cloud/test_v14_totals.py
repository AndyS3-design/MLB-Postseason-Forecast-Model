"""Model-implied total-run probability, no-vig half-run lines and archive tests."""
from __future__ import annotations
import json, math, unittest
from pathlib import Path
from v6_baseball_totals import HALF_RUN_LINES, half_run_line_probabilities, probabilities_for_line

ROOT=Path(__file__).resolve().parents[1]

class TotalRunProbabilitiesTests(unittest.TestCase):
    def test_half_run_odds_come_from_full_distribution_and_have_no_push(self):
        pmf={'1':.1,'3':.2,'5':.3,'7':.4}
        got=half_run_line_probabilities(pmf)
        self.assertEqual(tuple(float(k) for k in got),HALF_RUN_LINES)
        self.assertAlmostEqual(got['3.5']['under'],.3)
        self.assertAlmostEqual(got['3.5']['over'],.7)
        self.assertAlmostEqual(got['4.5']['under'],.3)
        self.assertAlmostEqual(got['5.5']['under'],.6)
        self.assertAlmostEqual(got['6.5']['over'],.4)
        for row in got.values():
            self.assertAlmostEqual(row['over']+row['under'],1)

    def test_malformed_distribution_does_not_get_reweighted_into_fake_odds(self):
        with self.assertRaises(ValueError):
            half_run_line_probabilities({'2':.1,'4':.1})
        with self.assertRaises(ValueError):
            half_run_line_probabilities({'3':-0.1,'4':1.1})
        with self.assertRaises(ValueError):
            half_run_line_probabilities({},[3.5])
        with self.assertRaises(ValueError):
            half_run_line_probabilities({'3':1},[4.0])

    def test_october_14_frozen_preliminary_probabilities_without_rewriting_it(self):
        # Regression on real V13 prelim saved before this presentation update.
        p=ROOT/'cloud_records/preliminary_revisions/849811_20261014T202744Z.json'
        if not p.exists():
            self.skipTest('2026-10-14 archived research preview missing')
        before=p.read_bytes()
        rec=json.loads(before)
        pmf=rec['total_distribution']
        calculated=half_run_line_probabilities(pmf)
        self.assertAlmostEqual(rec['expected_runs']['total'],7.4695,places=4)
        self.assertAlmostEqual(calculated['3.5']['under'],.14375,places=5)
        self.assertAlmostEqual(calculated['4.5']['under'],.207,places=5)
        self.assertAlmostEqual(calculated['5.5']['under'],.3524166667,places=5)
        self.assertAlmostEqual(calculated['6.5']['under'],.436,places=5)
        self.assertAlmostEqual(calculated['6.5']['over'],1-rec['under_6_5_probability'])
        grid=rec['score_grid']['cells']
        self.assertGreater(grid[3][2],grid[2][3])
        self.assertAlmostEqual(grid[3][2],.0523333333,places=5)
        self.assertEqual(p.read_bytes(),before)

if __name__=='__main__':
    unittest.main()
