"""Regression: never disguise a damaged SQLite project as a passing build."""
import hashlib
import json
import sqlite3
import pytest

from scripts.phase4_sqlite_rescue import RescueError, rescue


def make_source(tmp_path, broken_revision=False):
    p=tmp_path/'source.db'
    with sqlite3.connect(p) as db:
        db.executescript('''
        CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL,
            payload TEXT NOT NULL);
        CREATE TABLE revisions (project_id TEXT NOT NULL, version INTEGER NOT NULL,
            created_at REAL NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(project_id,version));
        ''')
        for version in range(1, 4):
            payload=json.dumps({'id':'P','name':'آزمایش','version':version,'long':'x'*100000})
            if version==3 and broken_revision:
                payload='THIS IS NOT VALID JSON'
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)',('P',version,float(version),payload))
            if version == 3:
                db.execute('INSERT INTO projects VALUES(?,?,?,?,?)',('P','آزمایش',version,3.,
                         json.dumps({'id':'P','name':'آزمایش','version':version,'long':'x'*100000})))
        db.commit()
    return p


def corrupt_overflow(tmp_path, source):
    # Deliberate overflow-page cycle reproduces SQLite's structural error.
    raw=bytearray(source.read_bytes());page_size=int.from_bytes(raw[16:18],'big')
    if page_size==1:page_size=65536
    offset=page_size;assert raw[offset]==0x0d
    assert int.from_bytes(raw[offset+3:offset+5],'big')==1
    cell=int.from_bytes(raw[offset+8:offset+10],'big')
    p=offset+cell
    def vnum(at):
        value=0
        for i in range(9):
            digit=raw[at+i];value=(value<<7)|(digit&0x7f)
            if digit<128:return value,i+1
        return value,9
    payload_size,k=vnum(p);_,m=vnum(p+k)
    usable=page_size;max_local=usable-35
    min_local=((usable-12)*32//255)-23
    assert payload_size>max_local
    local=min_local+((payload_size-min_local)%(usable-4))
    if local>max_local:local=min_local
    first=int.from_bytes(raw[p+k+m+local:p+k+m+local+4],'big')
    assert first>0
    visited=set();last=first
    while last:
        assert last not in visited
        visited.add(last)
        index=(last-1)*page_size
        nxt=int.from_bytes(raw[index:index+4],'big')
        if nxt==0:
            raw[index:index+4]=first.to_bytes(4,'big');break
        last=nxt
    source.write_bytes(raw)
    with sqlite3.connect('file:'+str(source)+'?mode=ro&immutable=1',uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]!='ok'
    return source


def test_corrupt_project_rescued_without_touching_source(tmp_path):
    bad=corrupt_overflow(tmp_path,make_source(tmp_path))
    before=hashlib.sha256(bad.read_bytes()).hexdigest()
    out=tmp_path/'repaired.db'
    result=rescue(bad,out)
    assert result['source_sha256']==before
    assert result['source_unchanged'] and result['revisions']==3
    assert hashlib.sha256(bad.read_bytes()).hexdigest()==before
    with sqlite3.connect(out) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        old=db.execute('SELECT payload FROM projects WHERE id=\'P\'').fetchone()[0]
        revision=db.execute('SELECT payload FROM revisions WHERE project_id=\'P\' AND version=3').fetchone()[0]
        assert old==revision
        assert json.loads(old)['version']==3


def test_fail_closed_if_unrecoverable_revision(tmp_path):
    bad=corrupt_overflow(tmp_path,make_source(tmp_path,broken_revision=True))
    with pytest.raises(RescueError,match='Damaged revision'):
        rescue(bad,tmp_path/'must-not-exist.db')
    assert not (tmp_path/'must-not-exist.db').exists()


def test_never_touches_healthy_source_or_overwrites_output(tmp_path):
    healthy=make_source(tmp_path)
    with pytest.raises(RescueError,match='healthy'):
        rescue(healthy,tmp_path/'output.db')
    bad=corrupt_overflow(tmp_path,healthy)
    out=tmp_path/'output.db';out.write_bytes(b'OTHER DATA')
    with pytest.raises(RescueError,match='new path'):
        rescue(bad,out)
    assert out.read_bytes()==b'OTHER DATA'


def test_mismatch_project_version_or_identity_blocks_recovery(tmp_path):
    bad=make_source(tmp_path)
    with sqlite3.connect(bad) as db:
        db.execute('UPDATE projects SET version=4 WHERE id=\'P\'')
    bad=corrupt_overflow(tmp_path,bad)
    with pytest.raises(RescueError,match='Incomplete revision'):
        rescue(bad,tmp_path/'result.db')
    assert not (tmp_path/'result.db').exists()
