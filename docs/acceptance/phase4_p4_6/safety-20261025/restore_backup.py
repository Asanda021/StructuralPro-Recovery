import json,hashlib,zipfile,subprocess,os,sys,sqlite3,shutil
from pathlib import Path
from contextlib import closing
archive=Path(sys.argv[1]);expected=sys.argv[2];dest=Path('/tmp/sp-safety-restored-20261025');dest.mkdir(exist_ok=False)
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist());z.extractall(dest)
m=json.loads((dest/'MANIFEST.json').read_text())
for name,r in m['files'].items():
 p=dest/name;assert p.stat().st_size==r['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
repo=dest/'repo';subprocess.run(['git','clone',str(dest/'code.bundle'),str(repo)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['git','fsck','--full'],cwd=repo,check=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==m['head']
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip()==m['tree']
source=Path(m['scenario_original_path']);held=source.with_name(source.name+'-held-safety-restore');assert not held.exists();source.rename(held)
try:
 shutil.copytree(dest/'scenario',source)
 tests=sorted(str(p.relative_to(repo)) for p in (repo/'tests').glob('test_phase4_sqlite*.py'))+['tests/test_phase4_site_acceptance.py']
 with (dest/'tests.log').open('w') as log:
  r=subprocess.run([sys.executable,'scripts/run_offline_tests.py','-q',*tests,'--junitxml='+str(dest/'tests.xml')],cwd=repo,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0
 # Use downloaded QA helper and cloned product, with original proof paths recreated only from archive.
 qa=repo/'docs/acceptance/phase4_p4_6/safety-20261025';qa.mkdir(parents=True)
 with (dest/'scenario.log').open('w') as log:
  r=subprocess.run([sys.executable,'scripts/run_offline_tests.py','-q',str(dest/'evidence/test_scenario_recovery.py'),'--junitxml='+str(dest/'scenario.xml')],cwd=repo,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},stdout=log,stderr=subprocess.STDOUT)
 assert r.returncode==0
finally:
 source.rename(dest/'source-path-replay');held.rename(source)
r={'archive_sha256':expected,'head':m['head'],'tree':m['tree'],'manifest_files':len(m['files']),'git_fsck':True,'tests_exit':0,'scenario_exit':0,'source_hidden_and_recreated_from_download':True,'status':'RESTORED SAFETY CHECKPOINT; PHASE4 PARTIAL'}
(dest/'receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
