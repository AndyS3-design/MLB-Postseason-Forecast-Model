"""Pure baseball run-total probabilities computed only from simulated score counts.

No market or betting prices are used in these calculations.
"""
from __future__ import annotations
import math

def probabilities_for_line(pmf, line):
    if not pmf:
        raise ValueError('No simulated runs distribution available')
    dist={int(k):float(v) for k,v in pmf.items()}
    if any(k<0 or not math.isfinite(v) or v<0 for k,v in dist.items()):
        raise ValueError('Invalid scoring distribution')
    if not math.isclose(sum(dist.values()), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError('Scoring distribution must sum to one')
    threshold=float(line)
    if not math.isfinite(threshold) or not 0<=threshold<=40:
        raise ValueError('Invalid run-total threshold')
    over=sum(v for runs,v in dist.items() if runs>threshold)
    under=sum(v for runs,v in dist.items() if runs<threshold)
    exact=sum(v for runs,v in dist.items() if runs==threshold)
    return {'over':over,'under':under,'push':exact,'line':threshold}


HALF_RUN_LINES = (3.5, 4.5, 5.5, 6.5)


def half_run_line_probabilities(pmf, lines=HALF_RUN_LINES):
    """No vig, no bookmaker prices: exact probabilities from one saved PMF.

    For a baseball final total (integer), half-run lines cannot push.
    This function never rescales the simulation or assumes a Poisson PMF.
    """
    out = {}
    for line in lines:
        threshold = float(line)
        if not (threshold * 2).is_integer() or threshold.is_integer():
            raise ValueError('Run total line must end in .5')
        v = probabilities_for_line(pmf, threshold)
        if not math.isclose(v['push'], 0.0, abs_tol=1e-10):
            raise ValueError('Half-run totals cannot push')
        out[f'{threshold:.1f}'] = {
            'under': v['under'],
            'over': v['over']
        }
    return out
