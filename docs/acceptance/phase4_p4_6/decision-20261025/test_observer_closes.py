"""Regression for diagnostic-only connection lifetime; no GC manipulation."""
import importlib.util,sqlite3,os
from pathlib import Path

def test_fresh_observer_explicitly_closes_connection(tmp_path,monkeypatch):
    out=tmp_path/'observer';monkeypatch.setenv('SP_SQLITE_OUT',str(out));monkeypatch.setenv('SP_SQLITE_ROOT',str(tmp_path/'scenario'));monkeypatch.setenv('SP_SQLITE_MODE','audited')
    spec=importlib.util.spec_from_file_location('diagnostic_worker',Path(__file__).resolve().parents[1]/'closure-20261025/sqlite_worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    db=tmp_path/'projects.db';c=sqlite3.connect(db);c.execute('create table sample(x)');c.commit();c.close()
    calls=[]
    class Connection(sqlite3.Connection):
        explicitly_closed=False
        def close(self):
            self.explicitly_closed=True
            return super().close()
    def connect(*args,**kw):
        kw['factory']=Connection;c=sqlite3.connect(*args,**kw);calls.append(c);return c
    worker.CONNECT=connect
    try:
        assert worker.fresh(db)['integrity']==[('ok',)]
        assert calls and all(c.explicitly_closed for c in calls), 'QA observer left a read-only connection open'
    finally:
        for c in calls:c.close()
        worker.log.close()
