"""Research audit invariants; no network required."""
import unittest,tempfile,csv
from pathlib import Path
from cloud.v8_audit import completed_games,metrics
class AuditTests(unittest.TestCase):
    def test_exact_cutoff_and_year(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mlb_postseason_2023_2026.csv'
            with p.open('w',newline='') as f:
                wr=csv.DictWriter(f,fieldnames=['year','game_id','date','first_pitch_utc','home','away','home_final','away_final'])
                wr.writeheader()
                wr.writerows([{'year':'2026','game_id':'1','date':'2026-10-12','first_pitch_utc':'2026-10-12T22:00:00Z','home':'MIL','away':'LAN','home_final':'2','away_final':'1'},
                              {'year':'2026','game_id':'2','date':'2026-10-13','first_pitch_utc':'2026-10-13T22:00:00Z','home':'MIL','away':'LAN','home_final':'3','away_final':'1'},
                              {'year':'2025','game_id':'3','date':'2025-10-12','first_pitch_utc':'2025-10-12T22:00:00Z','home':'MIL','away':'LAN','home_final':'5','away_final':'1'}])
            rows=completed_games(Path(d),'2026-10-13')
            self.assertEqual([r['game_id'] for r in rows],['1'])
    def test_known_metrics(self):
        rows=[{'home_won':1,'actual_total':5,'home_win':.7,'under':.6,'total':5.5,'no_post_home_win':.5,'no_post_under':.5,'no_post_total':8},
              {'home_won':0,'actual_total':8,'home_win':.4,'under':.3,'total':8.5,'no_post_home_win':.5,'no_post_under':.5,'no_post_total':8}]
        self.assertEqual(metrics(rows)['winner_accuracy'],1.)
        self.assertEqual(metrics(rows,False)['winner_accuracy'],.5)
        self.assertEqual(metrics(rows)['total_mae'],.5)
if __name__=='__main__':unittest.main()
