"""A healthy SQLite page tree can still contain damaged project history."""
import sqlite3
import pytest
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database, RecoveryError

def seed(tmp_path):
    path=tmp_path/'projects.db'
    store=ProjectStore(path)
    try:
        for idx in range(1,4):
            row=store.get('P') if idx>1 else {'name':'SYNTHETIC','quantity':'1.20'}
            row['quantity']=str(idx)
            store.save('P',row)
    finally: store.close()
    return path

@pytest.mark.parametrize('mutation',[
    "UPDATE projects SET payload='{broken' WHERE id='P'",
    "UPDATE projects SET version=77 WHERE id='P'",
    "UPDATE projects SET payload='{}' WHERE id='P'",
    "DELETE FROM revisions WHERE project_id='P' AND version=2",
    "INSERT INTO revisions(project_id,version,created_at,payload) VALUES('ORPHAN',1,0,'{}')",
])
def test_invalid_history_refused_on_open_and_backup(tmp_path,mutation):
    path=seed(tmp_path)
    with sqlite3.connect(path) as con:
        con.execute(mutation)
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with pytest.raises((RuntimeError,RecoveryError)):
        ProjectStore(path)
    target=tmp_path/'backup.db'
    with pytest.raises(RecoveryError):
        backup_database(path,target)
    assert not target.exists()

def test_healthy_history_still_opens_and_backs_up(tmp_path):
    path=seed(tmp_path)
    store=ProjectStore(path)
    try:assert store.get('P')['_meta']['version']==3
    finally:store.close()
    assert backup_database(path,tmp_path/'backup.db')['size']>0
    restored=ProjectStore(tmp_path/'backup.db')
    try:assert restored.get('P')['_meta']['version']==3
    finally:restored.close()
