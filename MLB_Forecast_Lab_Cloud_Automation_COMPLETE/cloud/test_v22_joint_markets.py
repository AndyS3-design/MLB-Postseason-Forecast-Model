"""V22: exact winner+Over markets and PRE-game-only grading."""
import unittest
import numpy as np
from datetime import datetime,timedelta,timezone
from v4_simulation import summarize
from cloud.v17_prospective import score_originals

NOW=datetime(2026,10,15,15,0,tzinfo=timezone.utc)

def original(*,late=False,include=True,corrupt=False):
    r={'game_id':'849999','date':'2026-10-15',
       'forecast_kind':'original_pregame',
       'forecast_created_utc':(NOW+timedelta(minutes=2 if late else -16)).isoformat(),
       'game_start_utc':NOW.isoformat(),
       'predicted_home_win':.6,'elo_home_win':.52,'expected_runs':{'total':7.},
       'total_distribution':{'4':.25,'5':.25,'8':.5},
       'official_final':{'home':5,'away':3}}
    if include:
        r['win_and_over_probabilities']={
          '4.5':{'home_win_and_over':.35,'away_win_and_over':.4,
                 'favorite_win_and_over':.35,'favorite_side':'home','over':.75},
          '5.5':{'home_win_and_over':.25,'away_win_and_over':.25,
                 'favorite_win_and_over':.25,'favorite_side':'home','over':.5}}
    if corrupt:r['win_and_over_probabilities']['5.5']['home_win_and_over']=.9
    return r

class JointTests(unittest.TestCase):
    def test_exact_score_draw_joint_probability_not_marginal_product(self):
        # 4 home victories (3 scores 3+2=5, one 4+3=7); two away
        # victories (5+2=7 twice); all games are final/non-tied.
        h=np.array([3,3,3,4,2,2],dtype=int)
        a=np.array([2,2,2,3,5,5],dtype=int)
        f=summarize({'home_final':h,'away_final':a})
        self.assertAlmostEqual(f['home_win_probability'],4/6)
        q=f['win_and_over_probabilities']
        self.assertAlmostEqual(q['4.5']['favorite_win_and_over'],4/6)
        self.assertAlmostEqual(q['4.5']['away_win_and_over'],2/6)
        self.assertAlmostEqual(q['5.5']['favorite_win_and_over'],1/6)
        self.assertAlmostEqual(q['5.5']['away_win_and_over'],2/6)
        self.assertAlmostEqual(q['5.5']['over'],.5)
        self.assertNotAlmostEqual(q['5.5']['favorite_win_and_over'],
                                  f['home_win_probability']*q['5.5']['over'])

    def test_away_favorite_and_invariant(self):
        h=np.array([3,2,2,2,1])
        a=np.array([2,4,4,4,4])
        f=summarize({'home_final':h,'away_final':a})
        q=f['win_and_over_probabilities']['5.5']
        self.assertEqual(q['favorite_side'],'away')
        self.assertAlmostEqual(q['favorite_win_and_over'],4/5)
        self.assertAlmostEqual(q['home_win_and_over']+q['away_win_and_over'],q['over'])

    def test_paired_original_scores_not_previews_and_not_backfilled(self):
        expected=.25**2
        v=score_originals([original()])
        self.assertEqual(v['winner_and_over_joint']['5.5']['n'],1)
        self.assertAlmostEqual(v['winner_and_over_joint']['5.5']['brier'],(1-.25)**2)
        self.assertEqual(v['winner_and_over_joint']['4.5']['n'],1)
        self.assertEqual(v['winner_and_over_joint']['4.5']['status'],'descriptive_only_insufficient_new_originals')
        old=score_originals([original(include=False)])
        self.assertEqual(old['winner_and_over_joint']['5.5']['n'],0)
        self.assertIsNone(old['winner_and_over_joint']['5.5']['brier'])
        late=score_originals([original(late=True)])
        self.assertEqual(late['unique_originals'],0)
        corrupted=score_originals([original(corrupt=True)])
        self.assertEqual(corrupted['winner_and_over_joint']['5.5']['n'],0)
        self.assertEqual(corrupted['winner_and_over_joint']['4.5']['n'],1)
        preview={**original(),'forecast_kind':'preliminary_pregame','game_id':'prelim'}
        v2=score_originals([original(),preview])
        self.assertEqual(v2['winner_and_over_joint']['5.5']['n'],1)

if __name__=='__main__':unittest.main()
