"""Unit checks for run-distribution scoring, exact game joins, and model guardrails."""
import unittest
import numpy as np
import pandas as pd
from robust_score_validation import (
    crps_discrete, discrete_interval, score_metrics,
    score_candidate, verify_exact_key_mapping, day_cluster_interval,
)
from backtest import ExtraInnings

class RobustScoreValidationTests(unittest.TestCase):
    def test_crps_point_mass(self):
        self.assertAlmostEqual(crps_discrete(np.array([0.,1.,0.]),1),0)
        self.assertAlmostEqual(crps_discrete(np.array([0.,1.,0.]),3),2)

    def test_intervals(self):
        p=np.array([.05,.1,.7,.1,.05])
        self.assertEqual(discrete_interval(p,.8),(1,3))
        with self.assertRaises(ValueError):discrete_interval(p,1.1)

    def test_score_matrix_pure(self):
        m=np.zeros((4,4));m[3,2]=.7;m[2,1]=.3
        r=score_metrics(m,3,2)
        self.assertEqual(r['exact_hit'],1)
        self.assertAlmostEqual(r['under_brier'],0.0)
        self.assertAlmostEqual(r['home_brier'],0.0)
        self.assertGreater(r['total_crps'],0)
        self.assertAlmostEqual(r['pi80_total_coverage'],1.0)

    def test_poisson_and_nb_probabilities(self):
        extra=ExtraInnings(home_win=.52,extra_pmf=np.array([0,.8,.2]),count=100)
        a=score_candidate(4.4,3.9,.1,.13,extra,.60,'poisson',4.2,4.0)
        b=score_candidate(4.4,3.9,.1,.13,extra,.60,'validated_nb',4.2,4.0)
        self.assertAlmostEqual(a.sum(),1)
        self.assertAlmostEqual(b.sum(),1)
        self.assertAlmostEqual(a[np.indices(a.shape)[0]>np.indices(a.shape)[1]].sum(),.60,places=5)
        self.assertGreater(np.sum(np.abs(a-b)),.01)
        with self.assertRaises(ValueError):score_candidate(4,4,.1,.1,extra,.5,'unknown',4,4)

    def test_exact_id_join(self):
        f=pd.DataFrame([{'game_id':'api-1'},{'game_id':'api-2'}])
        verify_exact_key_mapping(f,['api-1','api-2'],'x')
        with self.assertRaises(ValueError):verify_exact_key_mapping(f,['api-3'],'x')
        with self.assertRaises(ValueError):verify_exact_key_mapping(pd.concat([f,f]),['api-1'],'x')

    def test_bootstrap_not_claimed_for_tiny_postseason(self):
        records=[{'date':'2026-10-01','poisson_total_crps':1.0,
                  'validated_nb_total_crps':1.1} for _ in range(26)]
        self.assertIsNone(day_cluster_interval(records,'poisson','validated_nb','total_crps'))

if __name__=='__main__':unittest.main()
