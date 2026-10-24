"""A corrupted project DB must be refused *before* initialization can write DDL."""
import hashlib
import sqlite3
import pytest

from core.projects.store import ProjectStore
from tests.test_phase4_sqlite_rescue import make_source, corrupt_overflow


def test_corrupted_existing_database_refused_without_writes(tmp_path):
    src=corrupt_overflow(tmp_path,make_source(tmp_path))
    previous=hashlib.sha256(src.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match=r'(integrity|corrupt|سلامت|خراب)'):
        ProjectStore(src)
    assert hashlib.sha256(src.read_bytes()).hexdigest()==previous
    with sqlite3.connect(f'file:{src}?mode=ro&immutable=1',uri=True) as db:
        assert db.execute('PRAGMA quick_check').fetchone()[0]!='ok'


def test_healthy_existing_database_and_new_database_open(tmp_path):
    source=make_source(tmp_path)
    store=ProjectStore(source)
    try:
        assert store.get('P')['_meta']['version']==3
        assert store.integrity_check()['ok']
    finally: store.close()
    new=tmp_path/'new.db'
    store=ProjectStore(new)
    try:
        assert store.get('P') is None
        result=store.save('P',{'name':'SYNTHETIC'})
        assert result['version']==1
    finally:store.close()
    assert new.exists()
