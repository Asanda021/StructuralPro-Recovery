from pathlib import Path
import sqlite3,hashlib,json,sys
sys.path.insert(0,str(Path.cwd()))
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database
p=Path('/workspace/scratch/5ff2acae0199/site-scenario-original-corrupt/prior/engineering/db/projects.db');h=lambda:hashlib.sha256(p.read_bytes()).hexdigest()
r={'path':str(p),'sha256_before':h(),'bytes':p.stat().st_size,'inode':p.stat().st_ino,'device':p.stat().st_dev}
with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as c:
 r['integrity']=c.execute('pragma integrity_check').fetchall();r['journal_mode']=c.execute('pragma journal_mode').fetchone()[0];r['version']=c.execute('select version from projects').fetchall()
for label,fn in [('open',lambda:ProjectStore(p)),('backup',lambda:backup_database(p,p.parent/'REJECTED-new-backup.db'))]:
 try:fn();r[label]='UNEXPECTED SUCCESS'
 except Exception as e:r[label]={'rejected':True,'type':type(e).__name__,'message':str(e)}
r['sha256_after']=h();assert r['sha256_before']==r['sha256_after']=='561550b8d0bb42fb5bb3ec002222894414d2740c19f66d2cbb815728945793f6';assert not (p.parent/'REJECTED-new-backup.db').exists()
Path('docs/acceptance/phase4_p4_6/work-20261025/historical.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
