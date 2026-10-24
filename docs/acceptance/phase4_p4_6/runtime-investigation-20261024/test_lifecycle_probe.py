"""Exercise unchanged probes across project lifetimes; observe only at boundaries."""
import hashlib,json,os,sqlite3,sys
from pathlib import Path
import pytest

def runtime_snapshot(root,exception=None):
    db=root/'prior/engineering/db/projects.db'
    result={'pid':os.getpid(),'root':str(root),'sqlite':sqlite3.sqlite_version}
    if db.exists():
        result['file']={'inode':db.stat().st_ino,'size':db.stat().st_size,'sha256':hashlib.sha256(db.read_bytes()).hexdigest()}
        try:
            with sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True) as con:
                result['integrity']=con.execute('pragma integrity_check').fetchall()
                result['versions']=con.execute('select version,length(cast(payload as blob)) from projects').fetchall()
                result['last_revision']=con.execute('select max(version) from revisions').fetchone()[0]
        except Exception as e:result['read_error']=repr(e)
    try:
        result['fds']={p.name:os.readlink(p) for p in Path('/proc/self/fd').iterdir() if p.exists()}
        result['native_maps']=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if any(s in line.lower() for s in ('sqlite','ifcopenshell','libmupdf','pyside6','shiboken'))})
    except OSError as e:result['proc_error']=repr(e)
    if exception is not None:
        result['exception']=repr(exception);tb=exception.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_filename.endswith('phase4_site_operations_probe.py'):
                app=tb.tb_frame.f_locals.get('a')
                if app:
                    store=app.store
                    result['failure_store_path']=str(store.path)
                    result['cache_version']=store._cache.get('P',[None])[0]
                    try:result['in_transaction']=store.db.in_transaction
                    except Exception as e:result['connection_error']=repr(e)
            tb=tb.tb_next
    return result

@pytest.mark.parametrize('cycle',range(5))
def test_original_probe_across_project_lifetimes(cycle):
    from scripts.phase4_site_operations_probe import run
    base=Path(os.environ['STRUCTURALPRO_LIFECYCLE_ROOT'])
    root=base/('cycle-'+str(cycle))
    try:
        receipt=run(root)
        assert receipt['immutable_originals'] and receipt['reopen_equal']
    except BaseException as exception:
        (base/('cycle-'+str(cycle)+'-state.json')).write_text(json.dumps(runtime_snapshot(root,exception),ensure_ascii=False,indent=2))
        raise
    else:
        (base/('cycle-'+str(cycle)+'-state.json')).write_text(json.dumps(runtime_snapshot(root),ensure_ascii=False,indent=2))
