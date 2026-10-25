"""Deterministic concurrent writer at the backup validation boundary."""
import sqlite3
import pytest
from core.projects.store import ProjectStore
from core.recovery import recovery

def test_backup_validation_holds_one_read_snapshot(tmp_path,monkeypatch):
    path=tmp_path/'source.db';writer=ProjectStore(path);writer.save('P',{'name':'synthetic'})
    writer.db.execute('pragma busy_timeout=0');original=recovery._require_database_integrity;blocked=[]
    def integrity(c,*,label):
        original(c,label=label)
        if label=='source':
            try:writer.save('P',writer.get('P'))
            except sqlite3.OperationalError as e:
                assert e.sqlite_errorcode==sqlite3.SQLITE_BUSY;blocked.append(True)
    monkeypatch.setattr(recovery,'_require_database_integrity',integrity)
    try:
        backup=tmp_path/'backup.db';recovery.backup_database(path,backup)
        assert blocked, 'writer committed between backup validation reads; snapshot not pinned'
        check=ProjectStore(backup)
        try:assert check.get('P')['_meta']['version']==1
        finally:check.close()
    finally:writer.close()
