"""A corrupt database must never yield a backup reported as successful."""
import hashlib
import sqlite3
import pytest
from core.recovery.recovery import backup_database, RecoveryError, verify_database
from tests.test_phase4_sqlite_rescue import make_source, corrupt_overflow


def test_corrupt_input_refused_and_no_backup_created(tmp_path):
    original=corrupt_overflow(tmp_path, make_source(tmp_path))
    before=hashlib.sha256(original.read_bytes()).hexdigest()
    target=tmp_path/'should-not-exist.db'
    with pytest.raises(RecoveryError, match='integrity|corrupt|damaged'):
        backup_database(original,target)
    assert not target.exists()
    assert hashlib.sha256(original.read_bytes()).hexdigest()==before


def test_healthy_backup_is_verified_and_readable(tmp_path):
    original=make_source(tmp_path)
    target=tmp_path/'copy.db'
    receipt=backup_database(original,target)
    assert receipt['size']==target.stat().st_size
    assert verify_database(target)['ok']
    with sqlite3.connect(original) as a,sqlite3.connect(target) as b:
        assert a.execute('SELECT count(*) FROM revisions').fetchone()==b.execute('SELECT count(*) FROM revisions').fetchone()
        assert a.execute("SELECT payload FROM projects WHERE id='P'").fetchone()==b.execute("SELECT payload FROM projects WHERE id='P'").fetchone()
