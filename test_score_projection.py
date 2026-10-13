import unittest
from types import SimpleNamespace
import numpy as np
from score_projection import raw_final_score_matrix, align_winner_to_elo, project_score

class TestExactScore(unittest.TestCase):
    @staticmethod
    def extras():
        return SimpleNamespace(home_win=0.52,extra_pmf=np.array([0,.75,.2,.05]))
    def test_nonnegative_normalized_and_no_final_ties(self):
        m=raw_final_score_matrix(4,3.5,.15,.2,self.extras())
        self.assertAlmostEqual(m.sum(),1,places=10)
        self.assertGreaterEqual(m.min(),0)
        self.assertTrue(np.all(np.diag(m)==0))
    def test_elo_tilt_preserves_all_totals(self):
        m=raw_final_score_matrix(4.1,3.4,.18,.25,self.extras())
        h,a=np.indices(m.shape)
        for elo in (.15,.43,.57,.82):
            t=align_winner_to_elo(m,elo)
            self.assertAlmostEqual(t[h>a].sum(),elo,places=7)
            self.assertAlmostEqual(t.sum(),1,places=8)
            for total in range(22):
                self.assertAlmostEqual(m[h+a==total].sum(),t[h+a==total].sum(),places=9)
    def test_plausible_result(self):
        s=project_score(3.8,4.1,.1,.1,self.extras(),.6)
        self.assertAlmostEqual(s['home_win_probability'],.6,places=6)
        self.assertGreater(s['expected_home_final'],0)
        self.assertEqual(len(s['top_scores']),5)
        self.assertGreater(s['representative_favorite_score']['home_runs'],s['representative_favorite_score']['away_runs'])
    def test_missing_mu_rejected(self):
        with self.assertRaises(ValueError):
            project_score(float('nan'),3,.2,.2,self.extras(),.5)

if __name__ == '__main__':unittest.main()
