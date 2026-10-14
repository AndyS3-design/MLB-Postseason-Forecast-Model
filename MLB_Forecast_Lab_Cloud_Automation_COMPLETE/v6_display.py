"""Pure baseball-only formatting and scoreline invariants for a one-screen forecast.

This does not alter the simulated win or over/under probabilities.
"""
from __future__ import annotations
import math


def display_forecast(prediction: dict, away: str, home: str, total_line: float):
    """Return one internally consistent score, total, and probabilities.

    'Scoreline total' is the modal exact scoreline sum, NOT the mean
    of the simulation's total distribution. Show the mean only in methodology.
    """
    from v6_baseball_totals import probabilities_for_line
    score=prediction.get('v6_display_score')
    if not score:
        raise ValueError('V6 score metadata missing; install the updated v4_simulation.py')
    ah=int(score['away']); hh=int(score['home'])
    if ah==hh or ah<0 or hh<0:
        raise ValueError('A completed MLB score cannot be a tie or negative')
    if ah+hh!=int(score['total']):
        raise ValueError('Scoreline total mismatch')
    p_home=float(prediction['home_win_probability'])
    winner='home' if p_home>=.5 else 'away'
    # The modal exact score can favor a different team from the aggregation
    # of ALL simulated outcomes, so never force them to agree.
    pmf=probabilities_for_line(prediction['total_pmf'],float(total_line))
    if not math.isclose(sum(pmf[x] for x in ('over','under','push')),1.,abs_tol=1e-8):
        raise ValueError('Total distribution probabilities do not sum to 1')
    return dict(away=away,home=home,away_runs=ah,home_runs=hh,
      total=ah+hh,model_mean_total=float(prediction['total_expected_runs']),
      chosen_score_probability=float(score['probability']),
      winner=winner,winning_team=home if winner=='home' else away,
      winner_probability=p_home if winner=='home' else 1-p_home,
      displayed_score_winner=home if hh>ah else away,
      displayed_score_matches_model_favorite=((hh>ah)==(p_home>=.5)),
      **pmf)
