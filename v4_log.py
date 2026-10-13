"""Non-trading immutable-per-game local log; block records after scheduled first pitch."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import json,hashlib


def freeze(result,first_pitch_utc,now=None,destination=None):
    if not first_pitch_utc:raise ValueError('Official scheduled first pitch required')
    start=datetime.fromisoformat(str(first_pitch_utc).replace('Z','+00:00'))
    moment=now or datetime.now(timezone.utc)
    if moment.tzinfo is None:raise ValueError('Timezone-aware capture time required')
    if moment>=start:raise ValueError('Pregame forecast logging blocked after scheduled first pitch')
    game_id=str(result.get('match',{}).get('id') or '')
    if not game_id.isdigit():raise ValueError('Official numeric MLB game ID required')
    path=Path(destination or 'outputs/v4_pregame_forecasts.jsonl')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and json.loads(line)['game_id']==game_id:
                raise ValueError('A frozen forecast for this game already exists')
    record={'game_id':game_id,'recorded_at_utc':moment.isoformat(),
      'scheduled_first_pitch_utc':start.isoformat(),'model_version':result['model_version'],
      'home':result['home'],'away':result['away'],'date':result['date'],
      'forecast':result['forecast'],'model_training':result['training'],
      'data_gaps':result['data_gaps'],'adjustments':result['adjustments'],
      'lineup_confirmed':{side:len(result['personnel'][side]['lineup'])==9 for side in ('home','away')},
      'provenance':result['provenance']}
    raw=json.dumps(record,sort_keys=True,default=str)
    record['record_hash_sha256']=hashlib.sha256(raw.encode()).hexdigest()
    with path.open('a',encoding='utf-8') as file:file.write(json.dumps(record,sort_keys=True,default=str)+'\n')
    return record
