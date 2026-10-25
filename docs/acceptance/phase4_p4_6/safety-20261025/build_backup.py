import os,json,hashlib,shutil,subprocess,zipfile,tempfile
from pathlib import Path
repo=Path.cwd();root=Path(tempfile.mkdtemp(prefix='sp-safety-package-'));scenario=Path('/tmp/sp-decision-round2-scenario-20261025');qa=repo/'docs/acceptance/phase4_p4_6/safety-20261025'
subprocess.run(['git','bundle','create',str(root/'code.bundle'),'HEAD'],check=True)
shutil.copytree(scenario,root/'scenario');shutil.copytree(qa,root/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
m={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'scenario_original_path':str(scenario),'status':'PRODUCT SAFETY CHECKPOINT; PHASE4 PARTIAL','files':{}}
for p in sorted(root.rglob('*')):
 if p.is_file():m['files'][str(p.relative_to(root))]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(root/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
out=Path('/tmp/StructuralPro_SQLite_Safety_20261025.zip')
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(root.rglob('*')):
  if p.is_file():z.write(p,str(p.relative_to(root)))
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for name,r in m['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==r['sha256']
r={'path':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'manifest_files':len(m['files']),'head':m['head'],'tree':m['tree']}
Path('/tmp/sp-safety-archive.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
