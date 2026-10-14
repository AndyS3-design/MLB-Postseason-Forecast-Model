"""Historical 2020–25 totals distribution study reproducibility and separation."""
import math,unittest
from pathlib import Path
from cloud.v17_scoring_research import read_archive,prob,evaluate,run,EXPECTED_GAMES

ROOT=Path(__file__).resolve().parents[1]
class ScoreResearchTests(unittest.TestCase):
    def test_261_official_final_games_and_complete_chronology(self):
        games=read_archive(ROOT/'data/official_postseason_2020_2025.csv')
        self.assertEqual({y:len(v) for y,v in games.items()},EXPECTED_GAMES)
        output=run(ROOT/'data/official_postseason_2020_2025.csv')
        self.assertEqual(output['train_years'],[2021,2022])
        self.assertEqual(output['retrospective_later_years'],[2023,2024,2025])
        self.assertEqual(output['earlier_year_logloss_by_alpha']['0.0']['n'],77)
        self.assertEqual(output['later_year_comparison_by_alpha']['0.0']['n'],131)
        self.assertIn(output['selected_on_early_years_only'],(0.,.05,.10,.15,.20,.30,.40))

    def test_poisson_and_gamma_poisson_are_proper_run_distributions(self):
        for a in (0.,.05,.15,.4):
            probs=[prob(k,7.5,a) for k in range(180)]
            self.assertTrue(all(v>=0 and math.isfinite(v) for v in probs))
            self.assertAlmostEqual(sum(probs),1,places=7)
            self.assertAlmostEqual(sum(k*v for k,v in enumerate(probs)),7.5,places=4)

    def test_prior_seasons_only(self):
        games={2020:[10],2021:[2],2022:[999],2023:[1]}
        a=evaluate(games,(2021,),0.)
        b=evaluate({**games,2022:[0],2023:[9999]},(2021,),0.)
        self.assertEqual(a,b)
        self.assertAlmostEqual(a['predicted_mean'],10)
        self.assertEqual(a['n'],1)

if __name__=='__main__':unittest.main()
