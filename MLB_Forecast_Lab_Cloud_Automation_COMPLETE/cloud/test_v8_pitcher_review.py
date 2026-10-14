import unittest
from cloud.v8_pitcher_review import WEIGHTS
class PitcherWeightTests(unittest.TestCase):
 def test_candidates_bounded_and_include_original(self):
  self.assertEqual(WEIGHTS,(0.,.25,.5,.75,1.))
  self.assertTrue(all(0<=x<=1 for x in WEIGHTS))
if __name__=='__main__':unittest.main()
