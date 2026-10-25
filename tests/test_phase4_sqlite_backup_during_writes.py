"""Consistent SQLite backup snapshots during live ProjectStore writes."""
import sqlite3
import threading
import time

from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database


def test_backup_under_active_projectstore_writer_has_whole_revision_snapshot(tmp_path):
    database=tmp_path/'live.db'
    writer_store=ProjectStore(database)
    writer_store.save('P', {'name':'Synthetic test', 'marker':0, 'data':'y'*150000})
    writer_store.close()
    started=threading.Event()
    failures=[]

    def write_new_revisions():
        store=ProjectStore(database)
        try:
            for num in range(1,16):
                row=store.get('P')
                row['marker']=num
                store.save('P',row)
                started.set()
                time.sleep(0.005)
        except Exception as exc:
            failures.append(exc)
        finally:
            store.close()

    writer=threading.Thread(target=write_new_revisions)
    writer.start()
    assert started.wait(timeout=5)
    try:
        for n in range(5):
            snapshot=tmp_path/f'copy-{n}.db'
            backup_database(database,snapshot)
            with sqlite3.connect(snapshot) as con:
                assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                row=con.execute("SELECT version,payload FROM projects WHERE id='P'").fetchone()
                assert row and row[0]>=1
                last=con.execute('SELECT payload FROM revisions WHERE project_id=? AND version=?',('P',row[0])).fetchone()
                assert last and row[1]==last[0]
                assert con.execute("SELECT count(*) FROM revisions WHERE project_id='P'").fetchone()[0]==row[0]
    finally:
        writer.join(timeout=10)
    assert not writer.is_alive()
    assert not failures,repr(failures)
    with sqlite3.connect(database) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert con.execute("SELECT version FROM projects WHERE id='P'").fetchone()[0]==16
