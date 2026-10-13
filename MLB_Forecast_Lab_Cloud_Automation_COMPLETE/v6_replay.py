"""Protect historical-replay forecasts from postgame outcome and lineup leakage."""
from __future__ import annotations
from v6_strength import pregame_history_only

# Only independently meaningful schedule fields are passed to the estimator;
# never pass final score, winner, play-by-play, or an in-game score record.
ALLOWED=(
    'id','date','home','away','home_name','away_name','game_type','start_utc',
    'home_pitcher_id','away_pitcher_id','home_pitcher','away_pitcher',
    'home_pitcher_hand','away_pitcher_hand',
)


def clean_game_input(match,*,verified_pregame,historical_starters=False):
    match=dict(match)
    out={key:match[key] for key in ALLOWED if key in match}
    required=('date','home','away')
    if any(not out.get(k) for k in required):raise ValueError('Missing game identity')
    if not verified_pregame and not historical_starters:
        for key in ('home_pitcher_id','away_pitcher_id','home_pitcher_hand','away_pitcher_hand'):
            out[key]=''
        for key in ('home_pitcher','away_pitcher'):
            out[key]='Unverified at pregame cutoff'
    return out


def historical_cutoff_assets(assets,day):
    # Freeze model is 2023/24-trained; its game-by-game FEATURE HISTORY is cut off.
    # This makes selected-game and future results inaccessible to the estimator.
    return {**assets,'enriched':pregame_history_only(assets['enriched'],day)}
