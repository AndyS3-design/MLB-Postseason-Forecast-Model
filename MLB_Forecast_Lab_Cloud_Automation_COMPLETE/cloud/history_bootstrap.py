"""Incrementally fetch 2016–2022 Retrosheet game-log ZIPs (2016–2025 total).

These are public historical source files, not future results or betting data.
Downloads are atomic. The run model falls back to its legacy window if an
archive is unavailable, and explicitly reports the training-year coverage.
"""
from __future__ import annotations
from pathlib import Path
from urllib.request import Request,urlopen
import zipfile

FIRST_YEAR=2016
LAST_BOOTSTRAP_YEAR=2022
MAX_ZIP_BYTES=12_000_000

def ensure_history(data_dir:Path,fetcher=None):
    data_dir=Path(data_dir);data_dir.mkdir(parents=True,exist_ok=True)
    report={'available':[],'downloaded':[],'unavailable':{}}
    for year in range(FIRST_YEAR,LAST_BOOTSTRAP_YEAR+1):
        dest=data_dir/f'gl{year}.zip'
        text=data_dir/f'GL{year}.TXT'
        if text.exists() and text.stat().st_size>500_000:
            report['available'].append(year);continue
        if dest.exists():
            if valid_archive(dest,year):report['available'].append(year);continue
            # Never trust a broken partial archive.
            dest.unlink()
        tmp=dest.with_suffix('.partial')
        try:
            url=f'https://www.retrosheet.org/gamelogs/gl{year}.zip'
            if fetcher:
                fetcher(url,tmp)
            else:
                request=Request(url,headers={'User-Agent':'MLB Forecast Lab historical baseball research'})
                with urlopen(request,timeout=45) as stream, tmp.open('wb') as f:
                    size=0
                    while True:
                        chunk=stream.read(128*1024)
                        if not chunk:break
                        size+=len(chunk)
                        if size>MAX_ZIP_BYTES:raise ValueError('Archive exceeds safety size')
                        f.write(chunk)
            if not valid_archive(tmp,year):raise ValueError('Invalid Retrosheet game-log ZIP')
            tmp.replace(dest)
            report['available'].append(year);report['downloaded'].append(year)
        except Exception as exc:
            report['unavailable'][str(year)]=str(exc)[:160]
            tmp.unlink(missing_ok=True)
    return report

def valid_archive(path,year):
    try:
        with zipfile.ZipFile(path) as z:
            matching=[n for n in z.namelist() if n.lower().endswith(('.txt','.csv')) and str(year) in n]
            return bool(matching) and z.testzip() is None
    except (zipfile.BadZipFile,OSError):return False
