import unittest
from cloud.v8_recency_review import HALF_LIVES,ALPHAS
class RecencyReviewTests(unittest.TestCase):
 def test_prespecified_candidate_weights(self):
  self.assertEqual(HALF_LIVES,(2.0,3.0,5.0))
  self.assertIn(3.,HALF_LIVES)
  self.assertTrue(all(x>0 for x in HALF_LIVES))
  self.assertEqual(ALPHAS,(0.1,1.,10.))
if __name__=='__main__':unittest.main()
