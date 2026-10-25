"""Non-release Phase4 checkpoint, including separately labelled failed evidence."""
from pathlib import Path
import sys,subprocess,json,tempfile,shutil,zipfile,hashlib
repo=Path.cwd();qa=repo/'docs/acceptance/phase4_p4_6/work-20261025';scenario=Path('/tmp/structuralpro-final-20261025');out=Path(sys.argv[1]).resolve()
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
assert not git('status','--porcelain'),'Freeze all intended evidence first'
state=json.loads((qa/'full-final-state.json').read_text());assert state['exit_code']==0
with tempfile.TemporaryDirectory(prefix='sp-backup-20261025-') as tmp:
 root=Path(tmp);subprocess.run(['git','bundle','create',str(root/'code.bundle'),'HEAD',git('symbolic-ref','HEAD')],check=True)
 shutil.copytree(scenario,root/'scenario');shutil.copytree(qa,root/'evidence',ignore=shutil.ignore_patterns('__pycache__','full.xml','full-final.xml'))
 for origin,label in [('/workspace/scratch/5ff2acae0199/site-scenario-original-corrupt/prior/engineering/db/projects.db','FAILED-historical-323.db'),('/workspace/scratch/5ff2acae0199/site-final-20261025/prior/engineering/db/projects.db','FAILED-work-251.db')]:
  (root/'diagnostics').mkdir(exist_ok=True);shutil.copy2(origin,root/'diagnostics'/label)
 (root/'diagnostics/README.txt').write_text('CORRUPTED FORENSIC EVIDENCE ONLY. NEVER restore these as the scenario. Source database: scenario/prior/engineering/db/projects.db. Root cause UNRESOLVED; Phase4 PARTIAL.')
 for origin,label in [('/tmp/sp-docx-dashboard-20261025','docx-dashboard'),('/tmp/sp-docx-package-20261025','docx-package'),('/tmp/sp-office-offline-20261025','office-print')]:
  shutil.copytree(origin,root/'renders'/label)
 manifest={'scope':'Phase4 P4-6 synthetic Non-Windows checkpoint; PARTIAL; physical corruption risk unresolved; not release','head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),'tested_head':state['head'],'tested_tree':state['tree'],'scenario_original_path':str(scenario),'files':{}}
 for p in sorted(root.rglob('*')):
  if p.is_file():manifest['files'][str(p.relative_to(root))]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 (root/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(root.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(root))
 receipt={'file':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'snapshot_head':manifest['head'],'snapshot_tree':manifest['tree'],'tested_head':state['head'],'tested_tree':state['tree'],'manifest_files':len(manifest['files']),'status':'PARTIAL CHECKPOINT; NOT ACCEPTANCE'}
 out.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
