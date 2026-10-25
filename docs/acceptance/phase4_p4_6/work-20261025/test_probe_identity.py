import os,json,sqlite3,time
from pathlib import Path

def test_workspace_probe_file_identity():
    from core.projects.store import ProjectStore
    from scripts.phase4_site_operations_probe import run
    out=Path('docs/acceptance/phase4_p4_6/work-20261025/identity.jsonl')
    original=ProjectStore.save
    def snapshot(store,stage,exc=None):
        path=store.path.resolve();r={'stage':stage,'wall':time.time(),'path':str(path),'fds':[]}
        try:r['path_identity']=[path.stat().st_dev,path.stat().st_ino,path.stat().st_size]
        except OSError as e:r['stat_error']=str(e)
        for fd in Path('/proc/self/fd').iterdir():
            try:
                target=os.readlink(fd)
                if str(path) in target:
                    s=fd.stat();r['fds'].append({'fd':fd.name,'target':target,'identity':[s.st_dev,s.st_ino,s.st_size]})
            except OSError:pass
        if exc:r['exception']={'message':str(exc),'code':getattr(exc,'sqlite_errorcode',None),'name':getattr(exc,'sqlite_errorname',None)}
        with out.open('a') as f:f.write(json.dumps(r)+'\n')
    def save(store,*args,**kwargs):
        snapshot(store,'before-save')
        try:result=original(store,*args,**kwargs)
        except Exception as e:snapshot(store,'failed-save',e);raise
        snapshot(store,'after-commit');return result
    ProjectStore.save=save
    try:
        r=run('/workspace/scratch/5ff2acae0199/site-identity-20261025');assert r['reopen_equal']
    finally:ProjectStore.save=original
