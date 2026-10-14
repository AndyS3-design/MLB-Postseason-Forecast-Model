"""Evaluate genuine pregame original forecasts; revisions are not counted twice."""
import json,math
from datetime import datetime
from pathlib import Path
import numpy as np

def timestamp(x):return datetime.fromisoformat(str(x).replace('Z','+00:00'))
def valid_original(r):
    if r.get('forecast_kind')=='revised_pregame':return False
    try:
        t=timestamp(r['forecast_created_utc']);start=timestamp(r['game_start_utc'])
        return t.tzinfo is not None and start.tzinfo is not None and t<start
    except (KeyError,TypeError,ValueError):return False

def wilson(k,n,z=1.96):
    if not n:return None
    p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(max(0,mid-radius),4),round(min(1,mid+radius),4)]

def summary(records):
    originals=[r for r in records if valid_original(r)]
    settled=[r for r in originals if r.get('official_final')]
    lead=[(timestamp(r['game_start_utc'])-timestamp(r['forecast_created_utc'])).total_seconds()/60 for r in originals]
    coverage={'original_forecasts':len(originals),'settled_originals':len(settled),
        'mean_lead_minutes':round(float(np.mean(lead)),1) if lead else None,
        'within_8_to_30_minutes_fraction':round(sum(8<=m<=30 for m in lead)/len(lead),4) if lead else None,
        'both_starters_have_3plus_verified_starts_fraction':round(sum(
            min(int(r.get('health',{}).get('starter_pitcher_history',{}).get(s,0)) for s in ('home','away'))>=3
            for r in originals)/len(originals),4) if originals else None,
        'both_lineups_confirmed_fraction':round(sum(all(r.get('health',{}).get('lineups_confirmed',{}).get(s,False)
            for s in ('home','away')) for r in originals)/len(originals),4) if originals else None,
        'any_data_gaps_fraction':round(sum(bool(r.get('health',{}).get('data_gaps')) for r in originals)/len(originals),4) if originals else None}
    report={'status':'prospective_first_pitch_locked','coverage':coverage,
        'warnings':['Fewer than 30 settled games is a small sample; no strong accuracy claims.',
                    'Revised pregame versions are separate and cannot count as independent games.',
                    'GitHub schedules are best effort; 20-minute target is not guaranteed.']}
    if not settled:return {**report,'performance':{'n':0,'status':'Awaiting official final scores'}}
    p=np.array([r['predicted_home_win'] for r in settled],float)
    elo=np.array([r['elo_home_win'] for r in settled],float)
    y=np.array([float(r['official_final']['home']>r['official_final']['away']) for r in settled])
    actual=np.array([r['official_final']['home']+r['official_final']['away'] for r in settled],float)
    totals=np.array([r['expected_runs']['total'] for r in settled],float)
    under=np.array([r['under_6_5_probability'] for r in settled],float)
    team_err=np.array([(abs(r['expected_runs']['home']-r['official_final']['home'])+
                         abs(r['expected_runs']['away']-r['official_final']['away']))/2 for r in settled],float)
    k=int(np.sum((p>=.5)==y))
    performance={'n':len(settled),'correct_winner_fraction':round(k/len(settled),4),
        'winner_accuracy_wilson_95':wilson(k,len(settled)),
        'winner_brier':round(float(np.mean((p-y)**2)),5),
        'elo_brier':round(float(np.mean((elo-y)**2)),5),
        'under_6_5_brier':round(float(np.mean((under-(actual<=6))**2)),5),
        'run_mae_per_team':round(float(np.mean(team_err)),3),
        'total_run_mae':round(float(np.mean(abs(totals-actual))),3),
        'status':'preliminary: small sample' if len(settled)<30 else 'prospective, interpret uncertainty'}
    bins=[]
    for i in range(5):
        mask=(p>=i/5)&((p<((i+1)/5)) if i<4 else (p<=1))
        if np.any(mask):bins.append({'range':[i/5,(i+1)/5],'n':int(np.sum(mask)),
            'mean_forecast':round(float(np.mean(p[mask])),3),
            'actual_home_win_rate':round(float(np.mean(y[mask])),3)})
    performance['reliability_bins']=bins
    return {**report,'performance':performance}

def from_files(root):
    path=Path(root)/'cloud_records/predictions'
    rows=[]
    for file in sorted(path.glob('*.json')):
        try:rows.append(json.loads(file.read_text()))
        except (OSError,json.JSONDecodeError):pass
    return summary(rows)
