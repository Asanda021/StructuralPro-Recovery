import json,hashlib,sys,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from core.platform.application import StructuralProApp
from core.recovery.recovery import require_project_history_consistency
root=Path('/tmp/sp-closure-scenario-final');a=StructuralProApp(root/'prior/engineering/db');p=a.open_project('P');proofs=[]
def walk(x):
 if isinstance(x,dict):
  if isinstance(x.get('path'),str) and isinstance(x.get('sha256'),str):
   f=Path(x['path']);assert f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==x['sha256'];assert f.is_relative_to(root);proofs.append({'path':str(f),'sha256':x['sha256']})
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
walk(p);require_project_history_consistency(a.store.db)
assert len(p['project_schedule_tasks'])==15 and len(p['schedule_baselines'])==1
assert [r['actual'] for r in p['progress_reports']]==['12.500000','45.000000','75.000000']
issued=p['progress_reports'][-1];last=a.project_progress('P',as_of=issued['date']);assert [last[k] for k in ('planned','planned_current','actual','variance')]==['100.000000','92.500000','75.000000','-25.000000']
assert a.store.integrity_check()['ok'];r={'synthetic_origin':'Fresh unchanged repository fixture; none of the four absent old files replaced','version':p['_meta']['version'],'proof_occurrences':len(proofs),'distinct_proofs':sorted({x['path'] for x in proofs}),'historical_progress':{k:last[k] for k in ('planned','planned_current','actual','variance')},'history_guard':'PASS','sqlite_integrity':'ok','schedule_duration':a.project_schedule('P')['duration'],'activities':15,'receipt':json.loads((root/'receipt.json').read_text())};a.store.close()
Path('docs/acceptance/phase4_p4_6/closure-20261025/scenario-audit-final.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='receipt'},ensure_ascii=False))
