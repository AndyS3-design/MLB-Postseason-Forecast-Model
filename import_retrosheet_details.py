"""OPTIONAL real pitcher statistics + throwing hand importer from Retrosheet.

Download 2023-2025 season CSV ZIPs (or supply them in data/retrosheet_detail_zips).
Reads gameinfo, pitching and allplayers using the official documented fields:
https://www.retrosheet.org/downloads/csvcontents.html

Only historical game results are stored. MatchupModel uses every result strictly
AFTER its game date. A missing detailed stat remains missing; no invented ERA.

Run on internet-connected Windows machine:
  py import_retrosheet_details.py --years 2023 2024 2025
"""
from __future__ import annotations
import argparse,csv,io,json,zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen,Request

BASE='https://www.retrosheet.org/downloads/'
DETAIL_FIELDS=['date','home','away','side','game_num','game_id','pitcher_id','sp_hand','sp_outs','sp_er','sp_k','sp_bb','sp_hr','sp_pitches','bp_outs','bp_er','bp_pitches','pitchers_used','manager_id','manager_name']
DIRECTORY_FIELDS=['pitcher_id','name','hand','season','team']


def parse_date(v):
    s=str(v).strip()
    if len(s)>=10 and '-' in s:
        return s[:10]
    if len(s)>=8 and s[:8].isdigit():
        return datetime.strptime(s[:8],'%Y%m%d').date().isoformat()
    raise ValueError('Bad Retrosheet game date: '+repr(v))


def value(v):
    try:
        s=str(v).strip()
        return int(s) if s else 0
    except ValueError:return 0


def member_csv(archive,basename):
    candidates=[n for n in archive.namelist() if n.lower().endswith(basename.lower()) and not n.startswith('__MACOSX')]
    if not candidates:
        raise FileNotFoundError(f'{basename} not included in archive; members={archive.namelist()[:12]}')
    # Filenames can be prefixed with season/year or nested; CSV schema is authoritative.
    with archive.open(candidates[0]) as raw:
        text=io.TextIOWrapper(raw,encoding='utf-8-sig',errors='replace',newline='')
        return list(csv.DictReader(text))


def parse_season_zip(path,year):
    with zipfile.ZipFile(path) as z:
        gi=member_csv(z,'gameinfo.csv')
        pi=member_csv(z,'pitching.csv')
        ap=member_csv(z,'allplayers.csv')
    info={};directory={}
    for r in gi:
        try:
            if int(str(r.get('season') or year))!=year:continue
            d=parse_date(r['date']);home=r['hometeam'];away=r['visteam'];gid=r['gid']
        except (ValueError,KeyError):continue
        if not home or not away or home==away:continue
        # A date + teams tuple is NOT unique: doubleheaders can occur on the same day.
        # Prefer the documented game number; older extracts also encode it in gid.
        number=str(r.get('number') or '').strip()
        if not number:
            number=gid[-1] if gid[-1:].isdigit() else '0'
        info[gid]=(d,home,away,number)
    for r in ap:
        pid=str(r.get('id') or '').strip()
        if not pid:continue
        h=str(r.get('throw') or '').upper().strip()
        if h not in ('L','R'):h=''
        name=(' '.join([str(r.get('first') or '').strip(),str(r.get('last') or '').strip()])).strip()
        if name:
            directory[(pid,year,str(r.get('team') or ''))]={'pitcher_id':pid,'name':name,'hand':h,'season':year,'team':r.get('team','')}
    by_pitcher=defaultdict(list)
    for r in pi:
        gid=str(r.get('gid') or '')
        if gid not in info:continue
        stattype=str(r.get('stattype') or 'value').strip().lower()
        if stattype not in ('value',''):continue
        team=str(r.get('team') or '')
        if team not in info[gid][1:]:continue
        seq=value(r.get('p_seq'))
        if seq<=0:continue
        by_pitcher[(gid,team)].append(r)
    rows=[];skipped=0
    for (gid,team),pitchers in by_pitcher.items():
        d,home,away,number=info[gid];side='home' if team==home else 'away'
        starters=[r for r in pitchers if value(r.get('p_seq'))==1]
        if len(starters)!=1:skipped+=1;continue
        sp=starters[0];relievers=[r for r in pitchers if value(r.get('p_seq'))>1]
        pid=str(sp.get('id') or '')
        if not pid:skipped+=1;continue
        hand=next((v['hand'] for (k,y,t),v in directory.items() if k==pid and y==year and t==team),'')
        rows.append(dict(date=d,home=home,away=away,side=side,game_num=number,game_id=gid,pitcher_id=pid,sp_hand=hand,
          sp_outs=value(sp.get('p_ipouts')),sp_er=value(sp.get('p_er')),
          sp_k=value(sp.get('p_k')),sp_bb=value(sp.get('p_w')),
          sp_hr=value(sp.get('p_hr')),sp_pitches='',
          bp_outs=sum(value(r.get('p_ipouts')) for r in relievers),
          bp_er=sum(value(r.get('p_er')) for r in relievers),bp_pitches='',
          pitchers_used=len(pitchers),manager_id='',manager_name=''))
    return rows,list(directory.values()),{'year':year,'games_with_info':len(info),'rows':len(rows),'pitcher_groups_skipped':skipped}



def detail_key(record):
    """Unique per game and team side, including both games of a doubleheader.

    Legacy rows without an ID/number retain a separate identity and can only be
    matched to games when no doubleheader ambiguity exists.
    """
    base=(record['date'][:10],record['home'],record['away'],record['side'])
    gid=str(record.get('game_id') or '').strip()
    num=str(record.get('game_num') or '').strip()
    if gid:return base+('gid:'+gid,)
    if num:return base+('num:'+num,)
    return base+('legacy',)


def download(year,destination):
    if destination.exists():return
    url=f'{BASE}{year}/{year}csvs.zip'
    print(f'Downloading Retrosheet {year} season CSVs: {url}',flush=True)
    req=Request(url,headers={'User-Agent':'Personal MLB research model (educational)'})
    dest_tmp=destination.with_suffix('.partial')
    try:
        with urlopen(req,timeout=90) as src,dest_tmp.open('wb') as out:
            while True:
                block=src.read(1024*1024)
                if not block:break
                out.write(block)
        with zipfile.ZipFile(dest_tmp) as z:
            if z.testzip() is not None:raise ValueError('ZIP archive integrity check failed')
        dest_tmp.replace(destination)
    except Exception:
        dest_tmp.unlink(missing_ok=True)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--years',nargs='+',type=int,default=[2023,2024,2025])
    p.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'data')
    p.add_argument('--offline',action='store_true',help='Use downloaded year ZIP files without internet')
    args=p.parse_args();cache=args.data_dir/'retrosheet_detail_zips';cache.mkdir(parents=True,exist_ok=True)
    rows=[];directory=[];logs=[]
    for y in args.years:
        if y<2023 or y>2025:raise ValueError('The published source is checked for 2023–2025 only')
        path=cache/f'{y}csvs.zip'
        if not path.exists():
            if args.offline:raise FileNotFoundError(str(path))
            download(y,path)
        rec,people,log=parse_season_zip(path,y)
        rows.extend(rec);directory.extend(people);logs.append(log)
    # Merge with any existing 2026 MLB detailed records if present.
    path=args.data_dir/'advanced_pitching_details.csv'
    if path.exists():
        with path.open(newline='',encoding='utf-8') as f:
            rows=[r for r in csv.DictReader(f) if int(r['date'][:4]) not in args.years]+rows
    seen={}
    for r in rows:
        k=detail_key(r)
        if k in seen and seen[k]!=r:raise ValueError(f'Conflicting boxscore record: {k}')
        seen[k]=r
    args.data_dir.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=DETAIL_FIELDS,extrasaction='ignore');w.writeheader();w.writerows(seen.values())
    directory_path=args.data_dir/'pitcher_directory.csv'
    if directory_path.exists():
        with directory_path.open(newline='',encoding='utf-8') as f:
            directory=[r for r in csv.DictReader(f) if int(r.get('season') or 0) not in args.years]+directory
    bykey={(r['pitcher_id'],str(r['season']),r['team']):r for r in directory}
    with directory_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=DIRECTORY_FIELDS,extrasaction='ignore');w.writeheader();w.writerows(bykey.values())
    print(json.dumps({'actual_pitching_game_team_rows':len(seen),'directory_entries':len(bykey),'season_details':logs},indent=2))

if __name__=='__main__':main()
