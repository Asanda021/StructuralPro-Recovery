"""Diagnostic only: real commits, file identities and fresh-connection checks."""
import os,json,sqlite3,time,hashlib
from pathlib import Path

def test_workspace_file_identity_during_323_real_commits():
 from core.projects.store import ProjectStore
 p=Path('/workspace/scratch/5ff2acae0199/identity-stress-20261025.db');s=ProjectStore(p);out=Path('docs/acceptance/phase4_p4_6/work-20261025/identity-stress.jsonl')
 try:
  for n in range(1,324):
   r={'n':n,'wall':time.time(),'path_inode':p.stat().st_ino,'fds':[]}
   for fd in Path('/proc/self/fd').iterdir():
    try:
     target=os.readlink(fd)
     if str(p) in target:r['fds'].append({'fd':fd.name,'target':target,'inode':fd.stat().st_ino})
    except OSError:pass
   payload={'name':'SYNTHETIC diagnostic only','text':'x'*373950,'revision':n}
   try:s.save('P',payload)
   except Exception as e:r['error']={'code':getattr(e,'sqlite_errorcode',None),'name':getattr(e,'sqlite_errorname',None),'message':str(e)};raise
   finally:
    with out.open('a') as f:f.write(json.dumps(r)+'\n')
   time.sleep(.03)
 finally:s.close()
 with sqlite3.connect(p) as c:assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
