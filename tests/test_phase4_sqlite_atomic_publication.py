"""Atomic no-overwrite rules for SQLite backup and forensic recovery."""
import pytest
from core.projects.store import ProjectStore
from core.recovery.recovery import RecoveryError, backup_database
from scripts.phase4_sqlite_rescue import RescueError, rescue
from tests.test_phase4_sqlite_rescue import corrupt_overflow, make_source


def test_backup_publish_race_must_not_overwrite_other_writer(tmp_path, monkeypatch):
    original=make_source(tmp_path)
    target=tmp_path/'same-destination.db'
    import core.recovery.recovery as recovery
    original_link=recovery.os.link
    def raced_link(src, dst, *args, **kwargs):
        target.write_bytes(b'another owner of destination')
        return original_link(src, dst, *args, **kwargs)
    monkeypatch.setattr(recovery.os,'link',raced_link)
    with pytest.raises(RecoveryError,match='destination appeared'):
        backup_database(original,target)
    assert target.read_bytes()==b'another owner of destination'
    assert not list(tmp_path.glob('.db-backup-*'))


def test_rescue_publish_race_never_overwrites_existing_path(tmp_path,monkeypatch):
    original=corrupt_overflow(tmp_path,make_source(tmp_path))
    target=tmp_path/'recovered.db'
    import scripts.phase4_sqlite_rescue as rescue_module
    original_link=rescue_module.os.link
    def raced_link(src,dst,*args,**kwargs):
        target.write_bytes(b'competing writer data')
        return original_link(src,dst,*args,**kwargs)
    monkeypatch.setattr(rescue_module.os,'link',raced_link)
    with pytest.raises(RescueError,match='Output appeared'):
        rescue(original,target)
    assert target.read_bytes()==b'competing writer data'
    assert not list(tmp_path.glob('.rescue-*'))


def test_existing_truncated_zero_length_store_refused_without_initializing(tmp_path):
    path=tmp_path/'projects.db'
    path.touch()
    with pytest.raises(RuntimeError,match='existing project database is empty'):
        ProjectStore(path)
    assert path.read_bytes()==b''
    assert not (tmp_path/'projects.db-journal').exists()


def test_legitimate_new_database_still_initializes(tmp_path):
    path=tmp_path/'fresh.db'
    store=ProjectStore(path)
    try:
        assert store.save('P',{'name':'SYNTHETIC'})['version']==1
        assert store.integrity_check()['ok']
    finally:
        store.close()
