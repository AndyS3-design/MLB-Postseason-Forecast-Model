"""V28 read-only official-denominator prospective scorecard.

No forecasting, model fitting, selection on 2026 results, or modification of
immutable original predictions. Missed/invalid originals count as incorrect.
Probabilistic metrics are restricted to identical valid frozen games and labeled.
"""
from __future__ import annotations
import argparse, csv, json, math, hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

START = date(2026, 10, 14)
FIRST_N = 30
GAME_TYPES = {'F', 'D', 'L', 'W'}
API = 'https://statsapi.mlb.com/api/v1/schedule'
MLB_TO_RETRO = {108:'ANA',109:'ARI',110:'BAL',111:'BOS',112:'CHN',113:'CIN',114:'CLE',115:'COL',116:'DET',117:'HOU',118:'KCA',119:'LAN',120:'WAS',121:'NYN',133:'OAK',134:'PIT',135:'SDN',136:'SEA',137:'SFN',138:'SLN',139:'TBA',140:'TEX',141:'TOR',142:'MIN',143:'PHI',144:'ATL',145:'CHA',146:'MIA',147:'NYA',158:'MIL'}


def day(value):
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def timestamp(value):
    t = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('Naive timestamp')
    return t


def probability(value):
    if isinstance(value, bool):
        raise ValueError('Boolean probability')
    p = float(value)
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('Invalid probability')
    return p


def official_finals(payload, as_of):
    if not isinstance(payload, dict) or not isinstance(payload.get('dates'), list):
        raise ValueError('Official MLB response missing dates')
    found = {}
    for block in payload['dates']:
        for g in block.get('games', []):
            if g.get('gameType') not in GAME_TYPES or g.get('status', {}).get('abstractGameState') != 'Final':
                continue
            d = day(g.get('officialDate') or block['date'])
            if not START <= d < day(as_of):
                continue
            sides = g['teams']
            home, away = sides['home'], sides['away']
            hs, ass = home['score'], away['score']
            if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (hs, ass)) or hs == ass:
                raise ValueError('Invalid official final')
            gid = str(g['gamePk'])
            if not gid.isdigit():
                raise ValueError('Invalid official game ID')
            item = dict(game_id=gid, date=d.isoformat(), home=MLB_TO_RETRO[home['team']['id']],
                        away=MLB_TO_RETRO[away['team']['id']], home_final=hs, away_final=ass,
                        game_start_utc=g['gameDate'])
            timestamp(item['game_start_utc'])
            if gid in found and found[gid] != item:
                raise ValueError('Conflicting official game ID')
            found[gid] = item
    return sorted(found.values(), key=lambda g: (g['date'], g['game_start_utc'], g['game_id']))


def fetch_finals(as_of, fetcher=None):
    if fetcher is None:
        def fetcher(url):
            with urlopen(Request(url, headers={'User-Agent': 'MLB V28 prospective audit'}), timeout=35) as r:
                return json.load(r)
    games = {}
    cursor = START
    while cursor < day(as_of):
        stop = min(cursor + timedelta(days=30), day(as_of) - timedelta(days=1))
        url = API + '?' + urlencode(dict(sportId=1, startDate=cursor.isoformat(), endDate=stop.isoformat(),
                                         gameTypes=','.join(sorted(GAME_TYPES))))
        for g in official_finals(fetcher(url), as_of):
            if g['game_id'] in games and games[g['game_id']] != g:
                raise ValueError('Conflicting official final between API calls')
            games[g['game_id']] = g
        cursor = stop + timedelta(days=1)
    return sorted(games.values(), key=lambda g: (g['date'], g['game_start_utc'], g['game_id']))


def originals(root):
    saved, bad = {}, []
    for file in sorted((Path(root) / 'cloud_records/predictions').glob('*.json')):
        try:
            r = json.loads(file.read_text())
            gid = str(r['game_id'])
            if gid != file.stem or gid in saved:
                raise ValueError('Bad ID')
            saved[gid] = r
        except (OSError, ValueError, KeyError, TypeError):
            bad.append(file.name)
    return saved, bad


def older_year_prior(root):
    path = Path(root) / 'data/official_postseason_2020_2025.csv'
    totals, ids = [], set()
    with path.open(newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            yr = int(row['year'])
            if not 2020 <= yr <= 2025 or day(row['date']).year != yr or row['game_type'] not in GAME_TYPES:
                raise ValueError('Non-older-year or non-playoff baseline row')
            if row['game_id'] in ids:
                raise ValueError('Duplicate older-year baseline game')
            ids.add(row['game_id'])
            h, a = int(row['home_runs']), int(row['away_runs'])
            if h < 0 or a < 0 or h == a:
                raise ValueError('Invalid baseline score')
            totals.append(h + a)
    if not totals:
        raise ValueError('Missing older-year baseline')
    return {'n': len(totals), 'training_years': list(range(2020, 2026)),
            'mean_total': sum(totals)/len(totals),
            'over': {str(line): sum(t > line for t in totals)/len(totals) for line in (4.5, 5.5)}}


def validate(rec, g):
    if rec is None:
        return 'missing_original'
    try:
        if rec.get('forecast_kind') != 'original_pregame':
            return 'not_original'
        if any(str(rec.get(k)) != str(g[k]) for k in ('game_id', 'date', 'home', 'away')):
            return 'identity_mismatch'
        if timestamp(rec['forecast_created_utc']) >= min(timestamp(rec['game_start_utc']), timestamp(g['game_start_utc'])):
            return 'not_before_first_pitch'
        if day(rec['features_cutoff_exclusive']) > day(g['date']):
            return 'future_feature_cutoff'
        final = rec.get('official_final')
        if final is not None and (final.get('source') != 'Official MLB schedule API' or
                final.get('home') != g['home_final'] or final.get('away') != g['away_final']):
            return 'conflicting_saved_final'
        probability(rec['predicted_home_win'])
    except (ValueError, KeyError, TypeError, OverflowError):
        return 'invalid_original'
    return None


def pmf(rec):
    try:
        raw = rec['total_distribution']
        p = {int(k): probability(v) for k, v in raw.items()}
        if not p or len(p) != len(raw) or min(p) < 0 or abs(sum(p.values()) - 1) > 1e-6:
            return None
        return p
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
        return None


def metrics(ps, ys):
    n = len(ps)
    if not n:
        return {'n': 0, 'correct': None, 'accuracy': None, 'brier': None}
    k = sum((p >= .5) == bool(y) for p, y in zip(ps, ys))
    return {'n': n, 'correct': k, 'accuracy': round(k/n, 6),
            'brier': round(sum((p-y)**2 for p, y in zip(ps, ys))/n, 6)}


def frozen_v23(rec, main, elo):
    v = rec.get('research_winner_ensemble')
    if not isinstance(v, dict) or v.get('method') != 'v23_fixed_50_model_50_elo':
        return None
    try:
        p = probability(v['home_win_probability'])
        if (probability(v['model_weight']) != .5 or probability(v['elo_weight']) != .5 or
                not math.isclose(p, .5*(main+elo), abs_tol=1e-10, rel_tol=0)):
            return None
        return p
    except (ValueError, KeyError, TypeError, OverflowError):
        return None


def frozen_joint(rec, p, dist, line):
    item = (rec.get('win_and_over_probabilities') or {}).get(str(line))
    if not isinstance(item, dict):
        return None
    try:
        h, a = probability(item['home_win_and_over']), probability(item['away_win_and_over'])
        side = 'home' if p >= .5 else 'away'
        over = sum(v for k, v in dist.items() if k > line)
        favorite = probability(item['favorite_win_and_over'])
        if (item.get('method') != 'exact joint event frequency from same simulated final scores' or
                item.get('favorite_side') != side or abs(h+a-over) > .001 or
                abs(favorite-(h if side == 'home' else a)) > .001):
            return None
        return favorite
    except (ValueError, KeyError, TypeError, OverflowError):
        return None


def grade(games, saved, prior):
    missing, per_game, paired, shadows, totals = {}, [], [], [], []
    joints = {str(line): [] for line in (4.5, 5.5)}
    correct = 0
    for g in games:
        rec = saved.get(g['game_id'])
        reason = validate(rec, g)
        y = int(g['home_final'] > g['away_final'])
        total = g['home_final'] + g['away_final']
        item = {'game_id': g['game_id'], 'date': g['date'], 'status': reason or 'valid_original',
                'winner_correct': False}
        if reason:
            missing[reason] = missing.get(reason, 0) + 1
            per_game.append(item)
            continue
        p = probability(rec['predicted_home_win'])
        item['winner_correct'] = (p >= .5) == bool(y)
        correct += int(item['winner_correct'])
        try:
            elo = probability(rec['elo_home_win'])
        except (ValueError, KeyError, TypeError, OverflowError):
            missing['no_elo_on_valid_original'] = missing.get('no_elo_on_valid_original', 0) + 1
        else:
            paired.append((p, elo, y))
            v23 = frozen_v23(rec, p, elo)
            if v23 is not None:
                shadows.append((p, elo, v23, y))
        dist = pmf(rec)
        if dist is not None:
            totals.append((rec, p, dist, total))
            for line in (4.5, 5.5):
                j = frozen_joint(rec, p, dist, line)
                if j is not None:
                    joints[str(line)].append((j, int(item['winner_correct'] and total > line)))
        per_game.append(item)
    n = len(games)
    paired_out = {name: metrics([r[i] for r in paired], [r[2] for r in paired])
                  for name, i in [('original', 0), ('elo', 1)]}
    shadow_out = {name: metrics([r[i] for r in shadows], [r[3] for r in shadows])
                  for name, i in [('original', 0), ('elo', 1), ('v23', 2)]}
    lines = {}
    for line in (4.5, 5.5):
        key = str(line)
        ps = [sum(v for k, v in dist.items() if k > line) for _, _, dist, _ in totals]
        ys = [int(total > line) for _, _, _, total in totals]
        lines[key] = {'model_over': metrics(ps, ys),
                      'older_year_constant_over': metrics([prior['over'][key]]*len(ps), ys),
                      'realized_over_count': sum(ys),
                      'frozen_same_simulation_favorite_win_and_over': metrics(
                          [x for x, _ in joints[key]], [y for _, y in joints[key]])}
    run_pairs = []
    for rec, p, dist, actual in totals:
        try:
            run_pairs.append((actual, float(rec['expected_runs']['total'])))
        except (KeyError, ValueError, TypeError):
            continue
    return {'official_completed_games': n, 'correct_winners_including_missing_as_wrong': correct,
            'end_to_end_accuracy': round(correct/n, 6) if n else None,
            'missing_or_invalid_count': n - sum(x['status'] == 'valid_original' for x in per_game),
            'issues': missing, 'paired_winner_n': len(paired), 'paired_winner': paired_out,
            'v23_paired_n': len(shadows), 'v23_paired': shadow_out,
            'over_lines': lines, 'run_total': {'n': len(run_pairs),
                'model_mae': round(sum(abs(a-e) for a,e in run_pairs)/len(run_pairs),6) if run_pairs else None,
                'older_year_constant_mae': round(sum(abs(a-prior['mean_total']) for a,e in run_pairs)/len(run_pairs),6) if run_pairs else None},
            'per_game': per_game}


def build(games, saved, prior, as_of, unreadable=None):
    if games != sorted(games, key=lambda g: (g['date'], g['game_start_utc'], g['game_id'])):
        raise ValueError('Official games not chronological')
    if len({g['game_id'] for g in games}) != len(games):
        raise ValueError('Duplicate official games')
    all_games = grade(games, saved, prior)
    first = grade(games[:FIRST_N], saved, prior)
    n = first['official_completed_games']
    met = n == FIRST_N and first['end_to_end_accuracy'] >= .9
    return {'study': 'V28 official-denominator prospective postseason scorecard',
            'tracking_start': START.isoformat(), 'as_of_exclusive_et_date': day(as_of).isoformat(),
            'official_source': API, 'official_finals_sha256': hashlib.sha256(
                json.dumps(games, sort_keys=True).encode()).hexdigest(),
            'older_year_prior': prior, 'all_games_since_launch': all_games,
            'predeclared_first_30': first,
            'acceptance': {'first_30_completed': n == FIRST_N,
                           'correct_in_first_30': first['correct_winners_including_missing_as_wrong'],
                           'numeric_90pct_met_without_exclusions': bool(met),
                           'status': ('numeric_milestone_requires_independent_review' if met else
                                      'awaiting_30' if n < FIRST_N else 'below_90pct')},
            'unreadable_original_files': unreadable or [],
            'notes': ['Missing/invalid originals are wrong, not excluded from official denominator.',
                      'Brier, totals and V23 are scored on their own explicitly matched subsets.',
                      'Elo has no total-run forecast; older-year 2020–2025 fixed total frequencies are baseline.',
                      'No tuning on 2026 results; 27/30 is a numeric milestone, not proof of future 90% skill.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--as-of', type=day, default=datetime.now(ZoneInfo('America/New_York')).date())
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    games = fetch_finals(args.as_of)
    saved, unreadable = originals(args.root)
    report = build(games, saved, older_year_prior(args.root), args.as_of, unreadable)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print('V28_FULL_COHORT', json.dumps({'n': report['all_games_since_launch']['official_completed_games'],
        'correct': report['all_games_since_launch']['correct_winners_including_missing_as_wrong'],
        'paired_brier_n': report['all_games_since_launch']['paired_winner_n'],
        'first_30_status': report['acceptance']['status']}))

if __name__ == '__main__':
    main()
