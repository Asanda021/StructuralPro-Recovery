"""A corrupted project DB must be refused *before* initialization can write DDL."""
import hashlib
import sqlite3
from core.platform.identity import SystemIdentityProvider
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
    class UntrustedOwner:
        # Deterministic negative proof on both Windows and POSIX: no legacy
        # project may be claimed without an independently verified file owner.
        trusted_for_legacy_claim = False

        def current(self):
            return SystemIdentityProvider().current()

        def owns_path(self, identity, path):
            raise AssertionError("Untrusted owner must not be consulted")

    with pytest.raises(RuntimeError, match='audit integrity'):
        ProjectStore(source, identity_provider=UntrustedOwner())
    with sqlite3.connect(source) as db:
        assert db.execute('SELECT version FROM projects WHERE id=?',('P',)).fetchone()[0]==3
        assert db.execute('SELECT count(*) FROM revisions WHERE project_id=?',('P',)).fetchone()[0]==3
    # Real Windows owner SID or POSIX file UID is a separate positive proof.
    # This test does not synthesize elevated privileges or bypass the ACL.
    store=ProjectStore(source)
    try:
        assert store.get('P')['_meta']['version']==3
        assert store.integrity_check()['ok']
    finally:
        store.close()
    new=tmp_path/'new.db'
    store=ProjectStore(new)
    try:
        assert store.get('P') is None
        result=store.save('P',{'name':'SYNTHETIC'})
        assert result['version']==1
    finally:store.close()
    assert new.exists()
