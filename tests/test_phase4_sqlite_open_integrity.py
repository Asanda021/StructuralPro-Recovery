"""A corrupted project DB must be refused *before* initialization can write DDL."""
import hashlib
import sqlite3
import pytest

from core.projects.store import ProjectStore
from core.platform.identity import SystemIdentityProvider
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
    provider=SystemIdentityProvider()
    identity=provider.current()
    if not provider.owns_path(identity,source):
        with pytest.raises(RuntimeError,match='audit integrity'):
            ProjectStore(source)
        with sqlite3.connect(source) as db:
            assert db.execute('SELECT version FROM projects WHERE id=?',('P',)).fetchone()[0]==3
            assert db.execute('SELECT count(*) FROM revisions WHERE project_id=?',('P',)).fetchone()[0]==3
    else:
        store=ProjectStore(source)
        try:
            assert store.get('P')['_meta']['version']==3
            assert store.integrity_check()['ok']
            principal=store.current_principal('P')
            assert (principal.user_id,principal.role)==(identity.subject_id,'owner')
            assert store.verify_audit('P')
            assert store.audit_events('P')[-1]['reference']=='migration:legacy-file-owner'
        finally: store.close()
    new=tmp_path/'new.db'
    store=ProjectStore(new)
    try:
        assert store.get('P') is None
        result=store.save('P',{'name':'SYNTHETIC'})
        assert result['version']==1
    finally:store.close()
    assert new.exists()


@pytest.mark.parametrize('proof',['mismatch','unreadable'])
def test_unaudited_legacy_database_requires_owner_proof(tmp_path,monkeypatch,proof):
    source=make_source(tmp_path)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    def owner_check(self,identity,path):
        if proof=='unreadable':
            raise OSError('synthetic unavailable owner proof')
        return False
    monkeypatch.setattr(SystemIdentityProvider,'owns_path',owner_check)
    with pytest.raises(RuntimeError,match='audit integrity'):
        ProjectStore(source)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    with sqlite3.connect(source) as db:
        assert db.execute('SELECT version FROM projects WHERE id=?',('P',)).fetchone()[0]==3
        assert db.execute('SELECT count(*) FROM revisions WHERE project_id=?',('P',)).fetchone()[0]==3
