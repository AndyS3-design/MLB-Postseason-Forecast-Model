import unittest
from cloud.v8_bullpen_health import workload_summary
class BullpenTests(unittest.TestCase):
 def test_no_roster_is_unverified(self):
  r=workload_summary({'profiles':[{'roster_known':False,'pitches_last_3d':45,'likely_fatigued':True}]})
  self.assertFalse(r['roster_verified']);self.assertFalse(r['use_in_forecast'])
  self.assertEqual(r['total_reported_pitches_last_3d'],45)
 def test_confirmed_subset(self):
  r=workload_summary({'profiles':[
    {'roster_known':True,'roster_confirmed':True,'pitches_last_3d':20},
    {'roster_known':True,'roster_confirmed':False,'pitches_last_3d':70}]})
  self.assertEqual(r['total_reported_pitches_last_3d'],20)
  self.assertEqual(r['relievers_in_sample'],1)
if __name__=='__main__':unittest.main()
