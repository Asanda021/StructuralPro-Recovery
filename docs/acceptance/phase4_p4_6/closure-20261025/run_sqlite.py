"""Independent runs, sequential to avoid introducing competing test workloads."""
import os,sys,subprocess,hashlib,json,sqlite3,shutil,time
from pathlib import Path
repo=Path.cwd();qa=repo/'docs/acceptance/phase4_p4_6/closure-20261025';tag=sys.argv[1] if len(sys.argv)>1 else '';base=Path('/tmp/sp-sqlite-closure-20261025'+tag);base.mkdir(exist_ok=False)
old=[Path('/workspace/scratch/5ff2acae0199/site-final-20261025/prior/engineering/db/projects.db'),Path('/workspace/scratch/5ff2acae0199/site-scenario-original-corrupt/prior/engineering/db/projects.db')]
proof=[]
for p in old:
 raw=p.read_bytes()
 with sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True) as c:r=c.execute('pragma integrity_check').fetchall()
 proof.append({'path':str(p),'sha256_before':hashlib.sha256(raw).hexdigest(),'identity':[p.stat().st_dev,p.stat().st_ino],'integrity':r})
source_files=['core/projects/store.py','core/recovery/recovery.py','core/reports/exporters.py','core/reports/site_operations.py','core/reports/project_controls.py','core/reports/project_control_figures.py','scripts/phase4_site_operations_probe.py']
source_hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in source_files}
results=[]
cases=[('audited','tmp'),('audited','workspace')] if tag.startswith('-audited') else [('original','tmp'),('original','workspace'),('audited','tmp'),('audited','workspace')]
for mode,surface in cases:
 name=mode+'-'+surface;out=base/name
 root=(base/(name+'-scenario')) if surface=='tmp' else Path('/workspace/scratch/5ff2acae0199')/('sqlite-closure-'+name+tag)
 env={**os.environ,'QT_QPA_PLATFORM':'offscreen','SP_SQLITE_OUT':str(out),'SP_SQLITE_ROOT':str(root),'SP_SQLITE_MODE':mode}
 with (base/(name+'.log')).open('w') as log:
  run=subprocess.run([sys.executable,'scripts/run_offline_tests.py','-q',str(qa/'sqlite_worker.py'),'--junitxml='+str(base/(name+'.xml'))],env=env,stdout=log,stderr=subprocess.STDOUT)
 results.append({'name':name,'exit_code':run.returncode,'root':str(root)});print(json.dumps(results[-1]),flush=True)
for r in proof:r['sha256_after']=hashlib.sha256(Path(r['path']).read_bytes()).hexdigest();assert r['sha256_before']==r['sha256_after']
assert source_hashes=={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in source_files},'Source changed during controlled runs'
(base/'source.json').write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_sha256_before_and_after':source_hashes},indent=2))
(base/'historical.json').write_text(json.dumps(proof,indent=2));(base/'runs.json').write_text(json.dumps(results,indent=2));shutil.copytree(base,qa/('sqlite-runs'+tag),ignore=shutil.ignore_patterns('*-scenario'))
print(json.dumps({'runs':results,'historical_unchanged':True}),flush=True)
