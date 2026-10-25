"""Older revisions are recovery evidence and must be valid before opening/backup."""
import sqlite3
import pytest
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database, RecoveryError

def _db(tmp_path):
    path=tmp_path/'site.db'
    store=ProjectStore(path)
    try:
        for step in range(1,4):
            store.save('P',{'name':'SYNTHETIC','marker':step,'project_id':'P','text':'x'*350})
    finally:
        store.close()
    return path

@pytest.mark.parametrize('malformed',[
    'INVALID_JSON',
    '[1,2,3]',
    '{"name":"SYNTHETIC","project_id":"OTHER"}',
    '{"name":"SYNTHETIC","marker":NaN}',
])
def test_invalid_old_revision_refused_at_open_and_backup(tmp_path,malformed):
    path=_db(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE revisions SET payload=? WHERE project_id=? AND version=1',(malformed,'P'))
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with pytest.raises((RuntimeError,RecoveryError),match='history|revision|invalid|integrity'):
        ProjectStore(path)
    dest=tmp_path/'backup.db'
    with pytest.raises(RecoveryError,match='history|revision|invalid|integrity'):
        backup_database(path,dest)
    assert not dest.exists()

def test_healthy_old_history_backups_still_work(tmp_path):
    path=_db(tmp_path)
    store=ProjectStore(path)
    try:
        assert store.get('P')['_meta']['version']==3
    finally:
        store.close()
    target=tmp_path/'backup.db'
    assert backup_database(path,target)['size']>0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT count(*) FROM revisions').fetchone()[0]==3
