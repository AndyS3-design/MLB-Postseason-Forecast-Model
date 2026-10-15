"""Observed regulation-run targets must survive home inning exposure rules."""
import unittest

import numpy as np
from scipy.stats import skellam

from v4_simulation import _calibrate_home_intensity, play_games


def observed_regulation(draws):
    """reg_home preserves hypothetical ninths for the existing return API."""
    away=draws['reg_away'].sum(axis=1)
    home_eight=draws['reg_home'][:,:8].sum(axis=1)
    home=home_eight+np.where(home_eight<=away,draws['reg_home'][:,8],0)
    return home,away


class HomeInningExposureTests(unittest.TestCase):
    def assert_expected_mean(self,scores,target):
        # A reproducible, genuinely stochastic distribution check. The old
        # double suppression exceeds this interval for ordinary matchups.
        tolerance=5*float(np.std(scores,ddof=1))/np.sqrt(len(scores))+.002
        self.assertLess(abs(float(np.mean(scores))-target),tolerance)

    def test_actual_regulation_means_across_matchups_and_dispersions(self):
        for team,game in ((0.,0.),(.15,.05)):
            for h,a in ((3.2,5.6),(4.5,4.5),(6.1,3.3)):
                with self.subTest(home=h,away=a,team=team,game=game):
                    draws=play_games(h,a,n=200000,seed=408,
                                     alpha_team=team,alpha_game=game)
                    actual_h,actual_a=observed_regulation(draws)
                    self.assert_expected_mean(actual_h,h)
                    self.assert_expected_mean(actual_a,a)
                    self.assertGreater(draws['config']['latent_home_nine_inning_runs'],h)

    def test_unequal_starter_and_bullpen_inning_profiles(self):
        for sp,bp in ((2.7,6.8),(6.8,2.7)):
            with self.subTest(away_starter=sp,away_bullpen=bp):
                draws=play_games(5.2,3.8,n=200000,seed=672,
                    away_starter={'innings':7.1,'era':sp},
                    away_bullpen={'era':bp},away_manager_hook=6.4,
                    home_starter={'innings':3.4,'era':6.1},
                    home_bullpen={'era':3.2})
                h,a=observed_regulation(draws)
                self.assert_expected_mean(h,5.2)
                self.assert_expected_mean(a,3.8)

    def test_synthetic_oracle_refit_does_not_suppress_home_mean_again(self):
        # An oracle learns actual regulation means, not hypothetical runs in
        # an unplayed bottom ninth. Refitting that exact target must recover
        # the original latent scoring process instead of reducing it again.
        latent=4.5
        away=4.5
        oracle_target=latent-latent/9*skellam.sf(0,latent*8/9,away)
        draws=play_games(oracle_target,away,n=200000,seed=319,
                         alpha_team=0,alpha_game=0)
        self.assertAlmostEqual(draws['config']['latent_home_nine_inning_runs'],latent,places=8)
        h,a=observed_regulation(draws)
        self.assert_expected_mean(h,oracle_target)
        self.assert_expected_mean(a,away)

    def test_scenario_target_is_preserved_and_latent_is_not_clipped(self):
        draws=play_games(10.,3.,home_lineup=1.4,n=200000,seed=705)
        self.assertEqual(draws['config']['scenario_home_runs'],12.)
        self.assertGreater(draws['config']['latent_home_nine_inning_runs'],12.)
        h,a=observed_regulation(draws)
        self.assert_expected_mean(h,12.)
        self.assert_expected_mean(a,3.)

    def test_tiny_positive_dispersion_has_continuous_poisson_limit(self):
        base=(4.5,4.5,5.,1.,1.)
        for environment in (0.,.05,1e-18):
            exact=_calibrate_home_intensity(*base,0.,environment)[0]
            near_zero=_calibrate_home_intensity(*base,1e-18,environment)[0]
            self.assertAlmostEqual(near_zero,exact,places=8)

    def test_reproducible_without_seed_or_simulation_size_dependent_calibration(self):
        first=play_games(4.8,4.1,n=12000,seed=84)
        again=play_games(4.8,4.1,n=12000,seed=84)
        for key in ('home_final','away_final','reg_home','reg_away','extra_innings'):
            np.testing.assert_array_equal(first[key],again[key])
        other=play_games(4.8,4.1,n=13000,seed=19)
        key='latent_home_nine_inning_runs'
        self.assertEqual(first['config'][key],other['config'][key])
        self.assertIn('quadrature approximation',first['config']['home_calibration_method'])
        self.assertIn('scenario_home_runs / 9',first['config']['extra_innings_home_rate_policy'])
        self.assertTrue(np.all(first['home_final']!=first['away_final']))


if __name__=='__main__':unittest.main()
