"""Conservative, historical home-park run environment proxies (NOT causal)."""
from __future__ import annotations
import csv
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np


def park_training_factors(data_dir,years=(2023,2024)):
    """Train only 2023-24: park score relative to team/opponent run environment.

    Home team is used for lookup only if user confirms it is the same venue;
    relocations, renovations, neutral-site games break this assumption.
    """
    items=[]
    for year in years:
        p=Path(data_dir)/f'GL{year}.TXT'
        if not p.exists():continue
        with p.open(encoding='latin-1',newline='') as f:
            for r in csv.reader(f):
                if len(r)<21 or r[14].strip():continue
                try:ah=int(r[9]);hh=int(r[10])
                except (ValueError,IndexError):continue
                if ah<0 or hh<0:continue
                park=r[16];home=r[6];away=r[3]
                if not park or not home:continue
                items.append((park,home,away,ah+hh,year))
    if not items:return {}
    league=np.mean([x[3] for x in items]);bypark=defaultdict(list);homes=defaultdict(Counter)
    for park,home,away,total,year in items:
        bypark[park].append(total);homes[home][park]+=1
    vals={}
    for team,counter in homes.items():
        park,n=counter.most_common(1)[0]
        observed=np.mean(bypark[park]);mult=(observed*n+league*400)/(league*(n+400))
        vals[team]={'park_code':park,'games':len(bypark[park]),
            'factor':float(np.clip(mult,.92,1.08)),
            'label':'2023-24 home-park RUN ENVIRONMENT proxy; team quality confounded, not causal'}
    return vals
