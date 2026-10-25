"""Non-release Phase4 checkpoint, including separately labelled failed evidence."""
from pathlib import Path
import sys,subprocess,json,tempfile,shutil,zipfile,hashlib,os
repo=Path.cwd();qa=repo/'docs/acceptance/phase4_p4_6/closure-20261025';scenario=Path('/tmp/sp-closure-scenario-final');out=Path(sys.argv[1]).resolve()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
assert not git('status','--porcelain'),'Freeze all intended evidence first'
state=json.loads((qa/'full-final-state.json').read_text());assert state['exit_code']==0
with tempfile.TemporaryDirectory(prefix='sp-backup-20261025-') as tmp:
 root=Path(tmp);subprocess.run(['git','bundle','create',str(root/'code.bundle'),'HEAD',git('symbolic-ref','HEAD')],check=True)
 shutil.copytree(scenario,root/'scenario');shutil.copytree(qa,root/'evidence',ignore=shutil.ignore_patterns('__pycache__','full.xml','full-final.xml','*.db','*-journal','*-wal','*-shm','events.jsonl'))
 for origin,label in [('/workspace/scratch/5ff2acae0199/site-scenario-original-corrupt/prior/engineering/db/projects.db','FAILED-historical-323.db'),('/workspace/scratch/5ff2acae0199/site-final-20261025/prior/engineering/db/projects.db','FAILED-work-251.db'),('/workspace/scratch/5ff2acae0199/StructuralPro-Recovery/docs/acceptance/phase4_p4_6/closure-20261025/sqlite-runs-frozen/audited-workspace/failure-1792903116210965117/projects.db','FAILED-work-273-DBMOVED.db')]:
  (root/'diagnostics').mkdir(exist_ok=True);shutil.copy2(origin,root/'diagnostics'/label)
 (root/'diagnostics/README.txt').write_text('CORRUPTED FORENSIC EVIDENCE ONLY. NEVER restore these as the scenario. Source database: scenario/prior/engineering/db/projects.db. Root cause UNRESOLVED; Phase4 PARTIAL.')
 for origin,label in [('/tmp/sp-closure-render-final-20261025','office-print-and-official-docx')]:
  shutil.copytree(origin,root/'renders'/label)
 manifest={'scope':'Phase4 P4-6 synthetic Non-Windows checkpoint; PARTIAL; new readonly DBMOVED mechanism proven; actor/historical corruption unresolved; not release','head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'tested_head':state['head'],'tested_tree':state['tree'],'scenario_original_path':str(scenario),'files':{}}
 for p in sorted(root.rglob('*')):
  if p.is_file():manifest['files'][str(p.relative_to(root))]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 (root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 with tempfile.NamedTemporaryFile(prefix='sp-completed-20261025-',suffix='.zip',dir='/tmp',delete=False) as f:stage=Path(f.name)
 with zipfile.ZipFile(stage,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(root.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(root))
 with stage.open('rb') as f:os.fsync(f.fileno())
 with zipfile.ZipFile(stage) as z:
  assert z.testzip() is None
  for name,entry in manifest['files'].items():
   raw=z.read(name);assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256'],name
 os.link(stage,out) # Publish only closed, verified bytes; never replace.
 directory_fd=os.open(out.parent,os.O_RDONLY)
 try:os.fsync(directory_fd)
 finally:os.close(directory_fd)
 receipt={'stage_path':str(stage),'file':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'snapshot_head':manifest['head'],'snapshot_tree':manifest['tree'],'tested_head':state['head'],'tested_tree':state['tree'],'manifest_files':len(manifest['files']),'status':'PARTIAL CHECKPOINT; NOT ACCEPTANCE'}
 out.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
