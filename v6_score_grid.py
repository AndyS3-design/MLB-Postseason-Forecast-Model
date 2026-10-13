"""Readable HTML heatmap derived directly from sampled simulated FINAL scores."""
from __future__ import annotations
import html
from math import isfinite

def validate_grid(grid):
    cells=grid.get('cells')
    if not isinstance(cells,list) or len(cells)!=11 or any(not isinstance(r,list) or len(r)!=11 for r in cells):
        raise ValueError('Score grid must contain 11x11 probability cells')
    nums=[float(p) for row in cells for p in row]
    if any(not isfinite(p) or p<0 or p>1 for p in nums) or abs(sum(nums)-1)>1e-7:
        raise ValueError('Score grid is not a normalized probability distribution')
    return nums

def heatmap_html(grid, away, home, highlight=None):
    nums=validate_grid(grid)
    cap=max(max(nums),.0001)
    labels=[str(i) for i in range(10)]+['10+']
    fmt=lambda n:html.escape(str(n),quote=True)
    s=['<div class="v6-heat-scroller"><div class="v6-heat-table">']
    s.append('<div class="v6-grid-head v6-grid-corner">HOME ↓ &nbsp; AWAY →</div>')
    for v in labels:s.append(f'<div class="v6-grid-head">{v}</div>')
    hr,ar=(highlight or (None,None))
    for h,row in enumerate(grid['cells']):
        s.append(f'<div class="v6-grid-head">{labels[h]}</div>')
        for a,p in enumerate(row):
            # dark-teal to mint gradient. Normalization only changes color, not values.
            f=(float(p)/cap)**.72
            r=int(25+64*f);g=int(42+156*f);b=int(54+105*f)
            border=' v6-heat-active' if hr==h and ar==a else ''
            label=f'{fmt(home)} {labels[h]} · {fmt(away)} {labels[a]}: {float(p)*100:.2f}%'
            s.append(f'<div class="v6-heat-cell{border}" style="background:rgb({r},{g},{b})" title="{label}">{float(p)*100:.1f}</div>')
    s.append('</div></div>')
    s.append('<div class="v6-desc">Each number is a percentage of simulated final scores. 10+ means 10 or more runs. '
             'The outlined cell is the displayed score, when visible. The heatmap includes extra innings.</div>')
    return ''.join(s)
