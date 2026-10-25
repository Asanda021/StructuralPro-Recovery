"""Real SQLite file displacement; never infer recovery of unacknowledged writes."""
import hashlib,sqlite3,os
from pathlib import Path
from contextlib import closing
import pytest
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database,require_project_history_consistency

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(tmp_path):
    path=tmp_path/'projects.db';s=ProjectStore(path)
    s.save('P',{'name':'synthetic','exact':'0.000000000000000001','baseline':18,'current':20,'history':['12.5','45','75']})
    backup_database(path,tmp_path/'last-ack.db')
    s.close();return path

def displace(path):
    held=path.with_suffix('.live');replacement=path.parent/'replacement.db'
    replacement.write_bytes((path.parent/'last-ack.db').read_bytes())
    path.rename(held);replacement.rename(path)
    return held,sha(path)

def test_native_dbmoved_code(tmp_path):
    path=prepare(tmp_path)
    with closing(sqlite3.connect(path)) as c:
        c.execute('select * from projects').fetchall();held,h=displace(path)
        with pytest.raises(sqlite3.OperationalError) as e:c.execute("insert into revisions values('X',1,0,'{}')")
        assert (e.value.sqlite_errorcode,e.value.sqlite_errorname)==(1032,'SQLITE_READONLY_DBMOVED')
    assert sha(path)==h

@pytest.mark.parametrize('operation',['get','list','revisions','save','backup','integrity'])
def test_displaced_connection_refuses_success(tmp_path,operation):
    path=prepare(tmp_path);s=ProjectStore(path);p=s.get('P');held,h=displace(path)
    actions={'get':lambda:s.get('P'),'list':s.list,'revisions':lambda:s.revisions('P'),'save':lambda:s.save('P',p),'backup':lambda:s.backup(tmp_path/'wrong.db'),'integrity':s.integrity_check}
    try:
        with pytest.raises(RuntimeError,match='database identity'):actions[operation]()
        assert sha(path)==h and not (tmp_path/'wrong.db').exists()
        # No automatic reconnect or reset, even if the pathname is restored.
        path.rename(tmp_path/'replacement-held.db');held.rename(path)
        with pytest.raises(RuntimeError,match='database identity'):s.get('P')
    finally:s.close()

@pytest.mark.parametrize('stage',['before_commit','after_commit'])
def test_displacement_at_commit_never_acknowledged(tmp_path,monkeypatch,stage):
    path=prepare(tmp_path);connect=sqlite3.connect;trigger={'on':False};evidence={}
    class Connection(sqlite3.Connection):
        def commit(self):
            if trigger['on'] and stage=='before_commit':evidence['held'],evidence['hash']=displace(path)
            result=super().commit()
            if trigger['on'] and stage=='after_commit':evidence['held'],evidence['hash']=displace(path)
            return result
    def factory(*a,**k):k['factory']=Connection;return connect(*a,**k)
    monkeypatch.setattr(sqlite3,'connect',factory);s=ProjectStore(path);monkeypatch.setattr(sqlite3,'connect',connect)
    p=s.get('P');p['unacknowledged']='new';trigger['on']=True
    try:
        with pytest.raises(RuntimeError,match='database identity'):s.save('P',p)
    finally:s.close()
    assert sha(path)==evidence['hash']
    with closing(connect(path)) as c:require_project_history_consistency(c)
    restored=tmp_path/'restored.db';backup_database(tmp_path/'last-ack.db',restored)
    r=ProjectStore(restored)
    try:
        original=r.get('P');assert original['_meta']['version']==1 and 'unacknowledged' not in original
        assert original['history']==['12.5','45','75'] and original['exact']=='0.000000000000000001'
        assert r.save('P',original)['version']==2
    finally:r.close()
    r=ProjectStore(restored)
    try:assert r.get('P')['_meta']['version']==2 and r.integrity_check()['ok']
    finally:r.close()

@pytest.mark.parametrize('boundary',['BEGIN','projects','revisions'])
def test_displacement_inside_real_transaction(tmp_path,monkeypatch,boundary):
    path=prepare(tmp_path);connect=sqlite3.connect;trigger={'on':False};evidence={}
    class Connection(sqlite3.Connection):
        def execute(self,sql,*a,**kw):
            result=super().execute(sql,*a,**kw)
            match=sql.startswith('BEGIN') if boundary=='BEGIN' else sql.startswith('INSERT OR REPLACE INTO '+boundary+'(')
            if trigger['on'] and match:
                trigger['on']=False;evidence['held'],evidence['hash']=displace(path)
            return result
    def factory(*a,**k):k['factory']=Connection;return connect(*a,**k)
    monkeypatch.setattr(sqlite3,'connect',factory);s=ProjectStore(path);monkeypatch.setattr(sqlite3,'connect',connect)
    p=s.get('P');p['unacknowledged']='new';trigger['on']=True
    try:
        with pytest.raises((sqlite3.DatabaseError,RuntimeError)) as e:s.save('P',p)
        if isinstance(e.value,sqlite3.DatabaseError):assert e.value.sqlite_errorcode==1032
        with pytest.raises(RuntimeError,match='database identity'):s.get('P')
        with pytest.raises(RuntimeError,match='database identity'):s.backup(tmp_path/'unsafe.db')
        assert not (tmp_path/'unsafe.db').exists() and sha(path)==evidence['hash']
    finally:s.close()


def test_native_dbmoved_latches_failure_even_if_path_is_restored(tmp_path, monkeypatch):
    """A real SQLite 1032 must quarantine its connection despite rename-back.

    The path identity may match again before the application next calls stat().
    A SQLite 1032 is sufficient evidence that this connection must not resume.
    """
    path = prepare(tmp_path)
    real_connect = sqlite3.connect
    state = {"armed": False, "swapped": False}
    held = tmp_path / "original-held.db"
    swapped = tmp_path / "replacement-held.db"

    class RaceConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if state["armed"] and sql.startswith("INSERT OR REPLACE INTO projects("):
                state["armed"] = False
                new = tmp_path / "replacement-candidate.db"
                new.write_bytes((tmp_path / "last-ack.db").read_bytes())
                path.rename(held)
                new.rename(path)
                try:
                    return super().execute(sql, *args, **kwargs)
                finally:
                    path.rename(swapped)
                    held.rename(path)
                    state["swapped"] = True
            return super().execute(sql, *args, **kwargs)

    def connect(*args, **kwargs):
        kwargs["factory"] = RaceConnection
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)
    store = ProjectStore(path)
    monkeypatch.setattr(sqlite3, "connect", real_connect)
    old = store.get("P")
    old["unacknowledged"] = "never-publish"
    before = sha(path)
    state["armed"] = True
    try:
        with pytest.raises(sqlite3.OperationalError) as error:
            store.save("P", old)
        assert error.value.sqlite_errorcode == sqlite3.SQLITE_READONLY_DBMOVED
        assert state["swapped"] and sha(path) == before
        # Must remain blocked *even though the previous inode is restored*.
        with pytest.raises(RuntimeError, match="database identity"):
            store.get("P")
        with pytest.raises(RuntimeError, match="database identity"):
            store.backup(tmp_path / "forbidden.db")
        assert not (tmp_path / "forbidden.db").exists()
    finally:
        store.close()
