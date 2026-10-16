"""Regression tests for immutable forecasts with append-only official finals."""
import json
from pathlib import Path
import tempfile
import unittest
from cloud.v27_original_persistence import (
    ImmutableOriginalError, classify_change, remote_compatible, sync,
    validate_new_original,
)


def original(gid='849810'):
    return {
        'game_id':gid,'date':'2026-10-15','home':'LAN','away':'MIL',
        'forecast_kind':'original_pregame',
        'forecast_created_utc':'2026-10-15T23:31:25Z',
        'game_start_utc':'2026-10-16T00:00:00Z',
        'predicted_home_win':.49,'elo_home_win':.46,
        'total_distribution':{'5':.3,'6':.7},
        'win_and_over_probabilities':{'5.5':{'favorite_win_and_over':.34}},
    }


def settled(o, stamp='2026-10-16T03:00:00Z', home=4, away=6):
    d=json.loads(json.dumps(o))
    d['official_final']={
        'home':home,'away':away,'settled_at_utc':stamp,
        'source':'Official MLB schedule API',
    }
    d['evaluation']={'correct_winner':True,'winner_brier':.2401}
    return d


class MemoryRemote:
    def __init__(self, data=None):
        self.data=data or {}
        self.calls=[]
        self.conflict_once=False
    def get(self, path):
        rec=self.data.get(path)
        return (json.loads(json.dumps(rec[0])),rec[1]) if rec else None
    def put(self,path,rec,sha=None):
        self.calls.append((path,sha))
        if self.conflict_once:
            self.conflict_once=False
            return False
        existing=self.data.get(path)
        if (existing is None and sha is not None) or (existing and existing[1]!=sha):
            return False
        self.data[path]=(json.loads(json.dumps(rec)),'sha-'+str(len(self.calls)))
        return True


class PersistenceTests(unittest.TestCase):
    def test_identical_original_unchanged(self):
        self.assertEqual(classify_change(original(),original()),'unchanged')

    def test_first_official_final_allowed(self):
        self.assertEqual(classify_change(original(),settled(original())),'settlement_added')

    def test_pregame_forecast_fields_never_rewritten(self):
        for key,value in [
            ('predicted_home_win',.75),('elo_home_win',.80),
            ('game_start_utc','2026-10-16T01:00:00Z'),
            ('forecast_created_utc','2026-10-15T23:35:00Z'),
            ('total_distribution',{'6':1.}),
            ('win_and_over_probabilities',{'5.5':{'favorite_win_and_over':.99}}),
        ]:
            with self.subTest(key=key):
                changed=settled(original())
                changed[key]=value
                with self.assertRaisesRegex(ImmutableOriginalError,'Immutable original'):
                    classify_change(original(),changed)

    def test_settled_original_cannot_be_rewritten(self):
        old=settled(original())
        for changed in [
            original(),
            settled(original(),home=3),
            settled(original(),stamp='2026-10-16T04:00:00Z'),
        ]:
            with self.assertRaises(ImmutableOriginalError):
                classify_change(old,changed)

    def test_new_original_cannot_be_late_or_pre_settled(self):
        with self.assertRaisesRegex(ImmutableOriginalError,'post-first-pitch'):
            validate_new_original({**original(),'forecast_created_utc':'2026-10-16T00:01:00Z'},'849810.json')
        with self.assertRaises(ImmutableOriginalError):
            validate_new_original(settled(original()),'849810.json')

    def test_reject_fake_final_or_early_settlement(self):
        for bad in [
            settled(original(),home=6,away=6),
            settled(original(),stamp='2026-10-15T23:50:00Z'),
        ]:
            with self.assertRaises(ImmutableOriginalError):
                classify_change(original(),bad)

    def test_parallel_identical_final_keeps_first_timestamp(self):
        local=settled(original(),stamp='2026-10-16T04:00:00Z')
        saved=settled(original(),stamp='2026-10-16T03:00:00Z')
        self.assertEqual(remote_compatible(local,saved),'already_persisted')
        with self.assertRaisesRegex(ImmutableOriginalError,'Conflicting settled'):
            remote_compatible(local,settled(original(),home=2,away=6))

    def test_sync_appends_with_sha_and_retries_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions'
            folder.mkdir(parents=True)
            p=folder/'849810.json'
            p.write_text(json.dumps(settled(original())))
            path=p.relative_to(d).as_posix()
            remote=MemoryRemote({path:(original(),'existing-sha')})
            remote.conflict_once=True
            result=sync(d,remote,lambda _:original())
            self.assertEqual(result['settlements_appended'],1)
            self.assertEqual(remote.calls[0][1],'existing-sha')
            self.assertEqual(remote.calls[1][1],'existing-sha')

    def test_immutable_remote_conflict_has_no_write(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions'
            folder.mkdir(parents=True)
            p=folder/'849810.json'
            p.write_text(json.dumps(original()))
            remote=MemoryRemote({p.relative_to(d).as_posix():({**original(),'predicted_home_win':.99},'sha-x')})
            with self.assertRaises(ImmutableOriginalError):
                sync(d,remote,lambda _:original())
            self.assertEqual(remote.calls,[])

    def test_new_forecast_create_only_then_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions'
            folder.mkdir(parents=True)
            (folder/'849810.json').write_text(json.dumps(original()))
            remote=MemoryRemote()
            self.assertEqual(sync(d,remote,lambda _:None)['created'],1)
            self.assertEqual(sync(d,remote,lambda _:None)['already_persisted'],1)
            self.assertIsNone(remote.calls[0][1])

    def test_existing_forecast_deletion_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)/'MLB_Forecast_Lab_Cloud_Automation_COMPLETE/cloud_records/predictions'
            folder.mkdir(parents=True)
            (folder/'849810.json').write_text(json.dumps(original()))
            with self.assertRaisesRegex(ImmutableOriginalError,'disappeared'):
                sync(d,MemoryRemote(),lambda _:original())


if __name__=='__main__':
    unittest.main()
