"""Official hitter game-log inputs: strictly prior-day and verified team batting order."""
import json, unittest
from datetime import date
from urllib.parse import urlparse
from unittest.mock import patch

from cloud.official_hitter_history import (prior_hitter_profile,
                                             collect_verified_lineup_history)
from v4_sources import lineup_factor


def game(day,gid,ab=4,hits=2,game_type='R'):
    return {'date':day,'gameType':game_type,'game':{'gamePk':gid},
            'stat':{'atBats':ab,'baseOnBalls':1,'hitByPitch':0,
                    'sacFlies':0,'hits':hits,'doubles':1 if hits else 0,
                    'triples':0,'homeRuns':0}}

def snapshot():
    lineups={s:[{'id':n+1+(100 if s=='home' else 0),
                  'name':f'{s}-{n}','batting_hand':'R'} for n in range(9)]
             for s in ('home','away')}
    return {'is_official_lineup':{'home':True,'away':True},
            'confirmed_lineups':lineups}


class OfficialHitterHistoryTests(unittest.TestCase):
    def test_same_day_future_and_postseason_excluded_until_completed(self):
        payload={'stats':[{'splits':[
            game('2026-10-12',111),game('2026-10-13',112,game_type='L'),
            game('2026-10-14',113),game('2026-10-15',114),
            game('2026-10-11',110,game_type='S')]}]}
        seen=[]
        def fetch(url):
            seen.append(url)
            return payload
        result=prior_hitter_profile(1234,'2026-10-14',fetcher=fetch)
        self.assertEqual(result['observed_pa'],10)
        self.assertEqual(result['games'],2)
        self.assertEqual(result['cutoff_exclusive'],'2026-10-14')
        self.assertIn('2026',seen[0])
        self.assertTrue(result['estimated_woba']>0)

    def test_all_nine_verified_each_with_earlier_date_logs(self):
        snap=snapshot()
        def fetch(url):
            pid=int(url.split('/people/',1)[1].split('/',1)[0])
            return {'stats':[{'splits':[game(f'2026-09-{d:02d}',10000+pid*100+d)
                                         for d in range(1,11)]}]}
        result=collect_verified_lineup_history(snap,'2026-10-14',fetcher=fetch)
        self.assertEqual(result['status'],'verified_earlier_date_hitter_logs')
        self.assertEqual(result['prior_pa'],{'away':450,'home':450})
        self.assertEqual([x['id'] for x in result['by_side']['home']],
                         [x['id'] for x in snap['confirmed_lineups']['home']])
        for side in ('home','away'):
            factor=lineup_factor(snap['confirmed_lineups'][side],
                                 result['by_side'][side],'L')
            self.assertNotIn('fewer than 400',factor['status'])
            self.assertNotEqual(factor['factor'],1)

    def test_missing_one_player_cannot_partially_adjust_team(self):
        snap=snapshot()
        def fetch(url):
            if '/people/105/' in url:
                raise OSError('Temporary upstream unavailable')
            return {'stats':[{'splits':[game('2026-10-12',int(url.split('/people/')[1].split('/')[0]))]}]}
        out=collect_verified_lineup_history(snap,'2026-10-14',fetcher=fetch)
        self.assertEqual(out['status'],'official_history_unavailable')
        self.assertEqual(out['by_side'],{})
        self.assertEqual(len(out['errors']),1)

    def test_incomplete_or_duplicated_lineups_cannot_get_history(self):
        incomplete=snapshot()
        incomplete['confirmed_lineups']['away'].pop()
        self.assertEqual(collect_verified_lineup_history(incomplete,'2026-10-14')['status'],
                         'official_lineups_incomplete')
        dup=snapshot()
        dup['confirmed_lineups']['home'][1]['id']=dup['confirmed_lineups']['home'][0]['id']
        self.assertEqual(collect_verified_lineup_history(dup,'2026-10-14')['status'],
                         'invalid_official_lineup_ids')

    def test_conflicting_game_logs_rejected(self):
        payload={'stats':[{'splits':[game('2026-10-12',1,ab=4),
                                     game('2026-10-12',1,ab=5)]}]}
        with self.assertRaises(ValueError):
            prior_hitter_profile(123,'2026-10-14',fetcher=lambda url:payload)


if __name__=='__main__':unittest.main()
