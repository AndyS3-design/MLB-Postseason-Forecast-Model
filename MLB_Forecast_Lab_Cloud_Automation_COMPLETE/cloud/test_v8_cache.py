"""Validate cache freshness on historical-label changes, not 2026 updates."""
import unittest,tempfile
from types import SimpleNamespace
import pandas as pd
from cloud.v8_model_cache import load_or_train
from v4_matchup_core import FEATURES
class TestFrozenCache(unittest.TestCase):
    def test_cache_only_frozen_years(self):
        f=pd.DataFrame({c:[.5]*4 for c in FEATURES})
        f['year']=[2023,2024,2025,2026];f['game_type']=['R']*4;f['runs_actual']=[2.,3.,4.,5.]
        with tempfile.TemporaryDirectory() as d:
            calls=[]
            def trainer(_):
                calls.append(1)
                return SimpleNamespace(features=FEATURES,training_years=[2023,2024,2025],pipeline=1,training_rows=6)
            _,first=load_or_train(d,f,trainer)
            _,second=load_or_train(d,f,trainer)
            self.assertFalse(first['hit']);self.assertTrue(second['hit'])
            changed=f.copy();changed.loc[3,'runs_actual']=99.
            self.assertTrue(load_or_train(d,changed,trainer)[1]['hit'])
            changed.loc[2,'runs_actual']=99.
            self.assertFalse(load_or_train(d,changed,trainer)[1]['hit'])
            self.assertEqual(len(calls),2)

    def test_mutated_serialized_model_forces_refit(self):
        from pathlib import Path
        from cloud.v8_model_cache import NAME
        f=pd.DataFrame({c:[.5]*4 for c in FEATURES})
        f['year']=[2023,2024,2025,2026];f['game_type']=['R']*4;f['runs_actual']=[2.,3.,4.,5.]
        with tempfile.TemporaryDirectory() as d:
            n=[0]
            def trainer(_):
                n[0]+=1
                return SimpleNamespace(features=FEATURES,training_years=[2023,2024,2025],pipeline=1,training_rows=6)
            load_or_train(d,f,trainer)
            model=Path(d)/'outputs/v8_cache'/(NAME+'.joblib')
            model.write_bytes(model.read_bytes()+b'injected bytes')
            rebuilt=load_or_train(d,f,trainer)[1]
            self.assertFalse(rebuilt['hit'])
            self.assertEqual(n[0],2)
            self.assertTrue(load_or_train(d,f,trainer)[1]['hit'])

if __name__=='__main__':unittest.main()
