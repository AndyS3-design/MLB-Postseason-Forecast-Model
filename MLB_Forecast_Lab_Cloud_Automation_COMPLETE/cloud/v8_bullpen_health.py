"""Descriptive pregame reliever-workload evidence; not a run multiplier.
Only prior-date boxscores. Eligibility is verified only with official pregame roster.
"""
def workload_summary(bullpen):
    status=str((bullpen or {}).get('status') or 'No historical reliever sample')
    profiles=list((bullpen or {}).get('profiles') or [])
    roster_known=any(p.get('roster_known') for p in profiles)
    eligible=[p for p in profiles if p.get('roster_confirmed')] if roster_known else profiles
    with_pitches=[p for p in eligible if p.get('pitches_last_3d') is not None]
    return {'source':status,'roster_verified':roster_known,
        'historical_relievers_observed':len(profiles),'relievers_in_sample':len(eligible),
        'relievers_with_pitch_history':len(with_pitches),
        'relievers_flagged_as_fatigued':sum(bool(p.get('likely_fatigued')) for p in eligible),
        'total_reported_pitches_last_3d':sum(max(0,int(p.get('pitches_last_3d') or 0)) for p in with_pitches),
        'status':'official pregame roster subset' if roster_known else 'historical relievers only; active roster NOT confirmed',
        'use_in_forecast':False,
        'note':'Exploratory fatigue proxies are not independently fitted scoring multipliers.'}
def matchup_workload(personnel):
    return {side:workload_summary(personnel.get(side,{}).get('bullpen')) for side in ('home','away')}
