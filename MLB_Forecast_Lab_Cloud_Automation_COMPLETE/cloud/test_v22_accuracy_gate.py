"""V22 acceptance never upgrades retrospective selection into live accuracy."""
import unittest
from cloud.v22_accuracy_gate import evaluate

def row(i,correct=True):
    home_prob=.58 if correct else .42
    return {'game_id':str(800001+i),'date':'2026-10-12',
     'model_version':'18.0.0-forecast-integrity',
     'pregame_features_cutoff_exclusive':'2026-10-12',
     'actual_home_runs':'4','actual_away_runs':'2',
     'home_win_probability':str(home_prob),
     'elo_home_win_probability':'.54',
     'p_over_4_5':'.72','p_over_5_5':'.6',
     'p_pick_win_and_over_4_5':'.35',
     'p_pick_win_and_over_5_5':'.26'}

class AuditTests(unittest.TestCase):
    def test_19_of_30_is_not_ninety_percent(self):
        r=evaluate([row(i,i<19) for i in range(30)])
        self.assertEqual(r['target_wins_at_this_sample_size'],27)
        self.assertEqual(r['winner_correct'],19)
        self.assertEqual(r['more_correct_winners_needed'],8)
        self.assertFalse(r['retrospective_90pct_numeric_threshold_met'])
        self.assertFalse(r['can_claim_forward_accuracy_90pct'])
        self.assertEqual(r['model_pick_plus_over_5_5_hits'],19)
        self.assertEqual(r['elo_winners_correct'],30)
    def test_even_in_sample_27_of_30_cannot_claim_live_accuracy(self):
        r=evaluate([row(i,i<27) for i in range(30)])
        self.assertTrue(r['retrospective_90pct_numeric_threshold_met'])
        self.assertFalse(r['can_claim_forward_accuracy_90pct'])
    def test_omit_or_duplicate_or_backdate_a_match_is_error(self):
        data=[row(i) for i in range(30)]
        with self.assertRaisesRegex(ValueError,'all 30'):
            evaluate(data[:-1])
        duplicated=[dict(v) for v in data]
        duplicated[-1]['game_id']=data[0]['game_id']
        with self.assertRaisesRegex(ValueError,'Duplicate game'):
            evaluate(duplicated)
        tampered=[dict(v) for v in data]
        tampered[0]['pregame_features_cutoff_exclusive']='2026-10-13'
        with self.assertRaisesRegex(ValueError,'cutoff'):
            evaluate(tampered)
    def test_impossible_joint_probability_fails(self):
        rows=[row(i) for i in range(30)]
        rows[0]['p_pick_win_and_over_5_5']='.99'
        with self.assertRaisesRegex(ValueError,'Impossible joint'):
            evaluate(rows)

if __name__=='__main__':unittest.main()
