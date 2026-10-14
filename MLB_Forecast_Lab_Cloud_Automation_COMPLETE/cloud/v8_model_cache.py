"""Content-addressed cache for trusted frozen 2016-2025 Poisson fit only.
Do not load arbitrary/untrusted joblib files; the checksum below detects corruption,
not a malicious party who can edit both model binary and metadata. Fresh 2026 team and pitcher data
are reconstructed each matchup; no after-cutoff results are cached as features.
"""
import hashlib,json,os,tempfile,time
from pathlib import Path
import joblib,pandas as pd,sklearn
from v4_matchup_core import FEATURES,VERSION,train_frozen_run_model

SCHEMA=2

def file_digest(file):
    h=hashlib.sha256()
    with Path(file).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()
NAME='frozen_run_model_2016_2025'
def fingerprint(frame,code_file=None):
    code=Path(code_file) if code_file else Path(__file__).resolve().parents[1]/'v4_matchup_core.py'
    earlier=frame[(frame.game_type=='R')&(frame.year>=2016)&(frame.year<=2025)]
    if earlier.empty:raise ValueError('Cannot cache empty run training history')
    cols=['year','runs_actual',*FEATURES]
    if not set(cols).issubset(earlier.columns):raise ValueError('Missing run model features')
    h=hashlib.sha256()
    h.update(b'MLB-V8-FROZEN-v1');h.update(VERSION.encode());h.update(sklearn.__version__.encode())
    h.update(code.read_bytes())
    h.update(pd.util.hash_pandas_object(earlier[cols],index=False).values.tobytes())
    return h.hexdigest()

def load_or_train(root,frame,trainer=None):
    t=time.perf_counter();trainer=trainer or train_frozen_run_model
    folder=Path(root)/'outputs/v8_cache'
    model=folder/(NAME+'.joblib');manifest=folder/(NAME+'.json')
    digest=fingerprint(frame)
    if model.exists() and manifest.exists():
        try:
            d=json.loads(manifest.read_text())
            if (d.get('sha256')==digest and d.get('schema')==SCHEMA
                and d.get('sklearn_version')==sklearn.__version__
                and d.get('model_file_sha256')==file_digest(model)):
                fit=joblib.load(model)
                years=sorted(int(y) for y in frame[(frame.year>=2016)&(frame.year<=2025)&(frame.game_type=='R')].year.unique())
                if set(fit.features).issubset(FEATURES) and list(fit.training_years)==years and fit.pipeline:
                    return fit,{'hit':True,'sha256':digest,'load_or_fit_seconds':round(time.perf_counter()-t,3)}
        except (ValueError,TypeError,KeyError,AttributeError,EOFError,ImportError,OSError,json.JSONDecodeError):
            pass
    fit=trainer(frame)
    folder.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=folder,suffix='.joblib',delete=False) as f:tmp=Path(f.name)
    try:
        joblib.dump(fit,tmp);os.replace(tmp,model)
    finally:
        tmp.unlink(missing_ok=True)
    info={'schema':SCHEMA,'sha256':digest,'sklearn_version':sklearn.__version__,
          'training_years':fit.training_years,'training_rows':fit.training_rows,'version':VERSION,
          'model_file_sha256':file_digest(model)}
    temp=manifest.with_suffix('.json.tmp');temp.write_text(json.dumps(info,indent=2));os.replace(temp,manifest)
    return fit,{'hit':False,'sha256':digest,'load_or_fit_seconds':round(time.perf_counter()-t,3)}
