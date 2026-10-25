"""QA-only tracing; no engine, GC, timer or transaction policy changes."""
import os,sys,json,time,sqlite3,hashlib,gc,shutil,traceback
from pathlib import Path
from urllib.parse import urlparse,unquote
OUT=Path(os.environ['SP_SQLITE_OUT']);OUT.mkdir(parents=True,exist_ok=False)
ROOT=Path(os.environ['SP_SQLITE_ROOT']);MODE=os.environ['SP_SQLITE_MODE'];CONNECT=sqlite3.connect
log=(OUT/'events.jsonl').open('w',buffering=1)
def stat(p):
 try:
  s=Path(p).stat();return {'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size}
 except OSError as e:return {'error':str(e)}
def identity(p,initial=None):
 p=Path(p).resolve();r={'path':str(p),'identity':stat(p),'fds':[],'companions':{suffix:stat(str(p)+suffix) for suffix in ('-journal','-wal','-shm')}}
 for fd in Path('/proc/self/fd').iterdir():
  try:
   target=os.readlink(fd);s=stat(fd)
   if target==str(p) or target.startswith(str(p)+' (deleted)') or (initial and (s.get('device'),s.get('inode'))==initial):
    r['fds'].append({'fd':fd.name,'target':target,**s,'fdinfo':(Path('/proc/self/fdinfo')/fd.name).read_text()})
  except OSError:pass
 r['moved']=any((f.get('device'),f.get('inode'))!=(r['identity'].get('device'),r['identity'].get('inode')) for f in r['fds'])
 return r
def emit(event,path=None,**extra):
 r={'event':event,'wall_ns':time.time_ns(),'monotonic_ns':time.monotonic_ns(),**extra}
 if path:r.update(identity(path,extra.pop('initial',None)))
 log.write(json.dumps(r)+'\n')
def freeze(path,error,stage):
 dest=OUT/('failure-'+str(time.time_ns()));dest.mkdir()
 r={'stage':stage,'sqlite_errorcode':getattr(error,'sqlite_errorcode',None),'sqlite_errorname':getattr(error,'sqlite_errorname',None),'exception':repr(error),'identity':identity(path),'files':{}}
 for suffix in ('','-journal','-wal','-shm'):
  source=Path(str(path)+suffix)
  if source.is_file():
   raw=source.read_bytes();(dest/('projects.db'+suffix)).write_bytes(raw);r['files'][suffix]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
 (dest/'state.json').write_text(json.dumps(r,indent=2));emit('ERROR_FROZEN',path,**r)
def fresh(path):
 r={'identity':identity(path)}
 try:
  with CONNECT(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as c:
   r['journal_mode']=c.execute('pragma journal_mode').fetchone()[0];r['integrity']=c.execute('pragma integrity_check').fetchall()
   names={x[0] for x in c.execute('select name from sqlite_master where type="table"')}
   if {'projects','revisions'}<=names:
    r['active_tail']=c.execute('select p.id,p.version,cast(p.payload as blob)=cast(r.payload as blob) from projects p left join revisions r on p.id=r.project_id and p.version=r.version').fetchall()
    r['revision_count']=c.execute('select count(*) from revisions').fetchone()[0]
 except Exception as e:r['error']={'code':getattr(e,'sqlite_errorcode',None),'name':getattr(e,'sqlite_errorname',None),'message':str(e)}
 return r
class Observed(sqlite3.Connection):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.audit_path=Path(unquote(urlparse(str(args[0])).path) if str(args[0]).startswith('file:') else args[0]).resolve();s=self.audit_path.stat();self.initial=(s.st_dev,s.st_ino)
  emit('CONNECT_OR_REOPEN',self.audit_path,initial=self.initial,fresh=fresh(self.audit_path))
  self.set_trace_callback(self.trace)
 def trace(self,sql):
  op=sql.split(None,1)[0].upper() if sql.strip() else ''
  if op in ('BEGIN','INSERT','COMMIT','ROLLBACK'):
   emit('SQL_'+op,self.audit_path,initial=self.initial,statement=' '.join(sql.split()[:5]) if op!='INSERT' else 'INSERT '+('projects' if 'INTO projects' in sql else 'revisions' if 'INTO revisions' in sql else 'other'))
 def execute(self,*args,**kw):
  try:return super().execute(*args,**kw)
  except sqlite3.Error as e:freeze(self.audit_path,e,'execute-before-ProjectStore-rollback');raise
 def commit(self):
  try:result=super().commit()
  except sqlite3.Error as e:freeze(self.audit_path,e,'commit-before-ProjectStore-rollback');raise
  emit('COMMIT_RETURN',self.audit_path,initial=self.initial);return result
 def close(self):
  if hasattr(self,'audit_path'):
   emit('CLOSE_BEGIN',self.audit_path,initial=self.initial,in_transaction=self.in_transaction,fresh=fresh(self.audit_path))
   super().close();emit('CLOSE_RETURN',self.audit_path)
  else:super().close()
def test_independent_original_scenario():
 from scripts.phase4_site_operations_probe import run
 emit('ENV',python=sys.version,sqlite=sqlite3.sqlite_version,mode=MODE,root=str(ROOT),gc_enabled=gc.isenabled(),gc_threshold=gc.get_threshold(),pid=os.getpid())
 if MODE=='audited':
  def connect(*args,**kw):
   kw.setdefault('factory',Observed);return CONNECT(*args,**kw)
  sqlite3.connect=connect
 try:
  result=run(ROOT);r={'status':'PASS','receipt':result,'fresh':fresh(ROOT/'prior/engineering/db/projects.db')}
 except BaseException as e:
  db=ROOT/'prior/engineering/db/projects.db'
  if db.exists():freeze(db,e,'outer-probe-after-normal-product-error-handling')
  (OUT/'result.json').write_text(json.dumps({'status':'FAIL','exception':repr(e),'sqlite_errorcode':getattr(e,'sqlite_errorcode',None),'sqlite_errorname':getattr(e,'sqlite_errorname',None),'traceback':traceback.format_exc()},indent=2));raise
 finally:sqlite3.connect=CONNECT
 (OUT/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));emit('END',status='PASS');log.close()
