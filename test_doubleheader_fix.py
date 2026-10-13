"""Regression tests for same-day doubleheaders and legacy file compatibility."""
import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from import_retrosheet_details import parse_season_zip, detail_key
from import_mlb_boxscores import write_merged
from matchup_model import enrich_games, loaded_details


def csvdata(fields, rows):
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue()


class DoubleheaderTests(unittest.TestCase):
    def test_real_doubleheader_shape_preserves_both_starters(self):
        with TemporaryDirectory() as td:
            path=Path(td)/'2023csvs.zip'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('2023gameinfo.csv',csvdata(['gid','date','season','visteam','hometeam','number'],[
                    dict(gid='CHA202304181',date='2023-04-18',season=2023,visteam='PHI',hometeam='CHA',number=1),
                    dict(gid='CHA202304182',date='2023-04-18',season=2023,visteam='PHI',hometeam='CHA',number=2)]))
                pitches=[]
                for num in (1,2):
                    gid=f'CHA20230418{num}'
                    for team in ('CHA','PHI'):
                        pitches.append(dict(gid=gid,id=f'{team}_p{num}',team=team,p_seq=1,stattype='value',p_ipouts=15+num,p_er=num,p_k=5,p_w=1,p_hr=0))
                z.writestr('2023pitching.csv',csvdata(['gid','id','team','p_seq','stattype','p_ipouts','p_er','p_k','p_w','p_hr'],pitches))
                z.writestr('2023allplayers.csv',csvdata(['id','first','last','throw','team','season'],[]))
            records,_,_=parse_season_zip(path,2023)
            self.assertEqual(len(records),4)
            self.assertEqual({r['game_num'] for r in records},{'1','2'})
            self.assertEqual(len({detail_key(r) for r in records}),4)
            from import_retrosheet_details import DETAIL_FIELDS
            details_path=Path(td)/'advanced_pitching_details.csv'
            with details_path.open('w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=DETAIL_FIELDS);writer.writeheader();writer.writerows(records)
            details,_,_=loaded_details(Path(td))
            games=[dict(date='2023-04-18',home='CHA',away='PHI',game_num=str(n),home_sp='old',away_sp='old') for n in (1,2)]
            enriched,count=enrich_games(games,details,{})
            self.assertEqual(count,4)
            self.assertEqual([x['home_sp_er'] for x in enriched],[1.0,2.0])
            self.assertEqual([x['home_sp'] for x in enriched],['CHA_p1','CHA_p2'])

    def test_legacy_single_game_without_number_still_joins(self):
        games=[dict(date='2023-05-03',home='CHA',away='PHI',game_num='0')]
        row=dict(date='2023-05-03',home='CHA',away='PHI',side='home',pitcher_id='A',sp_er='2')
        enriched,count=enrich_games(games,{('2023-05-03','CHA','PHI','home'):row},{})
        self.assertEqual(count,1)
        self.assertEqual(enriched[0]['home_sp_er'],2)

    def test_legacy_ambiguous_doubleheader_does_not_join(self):
        games=[dict(date='2023-04-18',home='CHA',away='PHI',game_num=str(i)) for i in (1,2)]
        row=dict(date='2023-04-18',home='CHA',away='PHI',side='home',pitcher_id='A',sp_er='2')
        enriched,count=enrich_games(games,{('2023-04-18','CHA','PHI','home'):row},{})
        self.assertEqual(count,0)

    def test_mlb_game_ids_survive_same_day_merging(self):
        with TemporaryDirectory() as td:
            base=dict(date='2026-07-01',home='CHA',away='PHI',side='home',sp_er='1')
            rows=[dict(base,game_id=str(i),pitcher_id=f'p{i}') for i in (111,112)]
            write_merged(Path(td),rows,[])
            details,_,_=loaded_details(Path(td))
            games=[dict(date='2026-07-01',home='CHA',away='PHI',game_id=i) for i in (111,112)]
            enriched,count=enrich_games(games,details,{})
            self.assertEqual(count,2)
            self.assertEqual([r['home_sp'] for r in enriched],['p111','p112'])


if __name__=='__main__':unittest.main()
