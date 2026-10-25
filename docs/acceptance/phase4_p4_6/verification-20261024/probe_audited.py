"""Observe SQLite after original saves/reports/close; never change production data."""
import hashlib,json,os,sqlite3
from pathlib import Path

def test_original_probe_with_persistence_observations(monkeypatch):
    from core.projects.store import ProjectStore
    from core.platform.application import StructuralProApp
    from scripts.phase4_site_operations_probe import run
    root=Path(os.environ['STRUCTURALPRO_QA_SCENARIO'])
    root.mkdir(parents=True,exist_ok=False)
    trace=(root/'persistence-trace.jsonl').open('w')
    original_save=ProjectStore.save;original_close=ProjectStore.close
    original_report=StructuralProApp.site_report
    def check(store,stage):
        if not store.path.exists():return
        with sqlite3.connect(store.path.resolve().as_uri()+'?mode=ro',uri=True) as connection:
            check=connection.execute('pragma integrity_check').fetchone()[0]
            row=connection.execute('select version,cast(payload as blob) from projects where id=?',('P',)).fetchone()
        record={'stage':stage,'path':str(store.path),'integrity':check,'version':row[0] if row else None,'payload_sha256':hashlib.sha256(row[1]).hexdigest() if row else None}
        trace.write(json.dumps(record)+'\n');trace.flush()
        assert check=='ok',record
        if row:
            data=json.loads(row[1]);cached=store._cache.get('P')
            if cached:
                expected=dict(cached[1]);expected.pop('_meta',None)
                assert row[0]==cached[0] and data==expected,record
    def save(store,*args,**kwargs):
        result=original_save(store,*args,**kwargs);check(store,'save');return result
    def close(store):
        check(store,'before_close');result=original_close(store);check(store,'after_close');return result
    def report(app,*args,**kwargs):
        result=original_report(app,*args,**kwargs);check(app.store,'report:'+str(args[1:3]));return result
    monkeypatch.setattr(ProjectStore,'save',save)
    monkeypatch.setattr(ProjectStore,'close',close)
    monkeypatch.setattr(StructuralProApp,'site_report',report)
    try:result=run(root);assert result['immutable_originals'] and result['reopen_equal']
    finally:trace.close()
