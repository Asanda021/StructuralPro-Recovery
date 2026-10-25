"""Full offline QA; publish only closed log/JUnit files from a private tmp root."""
import subprocess,sys,os,time,json,gzip,hashlib,shutil
from pathlib import Path
qa=Path(__file__).resolve().parent;tmp=Path('/tmp/sp-closure-full-final-20261025');tmp.mkdir(exist_ok=False)
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip();started=time.time()
with (tmp/'full.log').open('w') as log:
 p=subprocess.Popen([sys.executable,'scripts/run_offline_tests.py','-q','--junitxml='+str(tmp/'full.xml')],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'})
 observed_pid=p.pid
 for candidate in Path('/proc').iterdir():
  if not candidate.name.isdigit():continue
  try:
   cmd=(candidate/'cmdline').read_bytes()
   if b'scripts/run_offline_tests.py' in cmd and str(tmp/'full.xml').encode() in cmd:observed_pid=int(candidate.name);break
  except OSError:pass
 sampler=subprocess.Popen([sys.executable,'docs/acceptance/phase4_p4_6/verification-20261024/host-sampler.py',str(observed_pid),str(tmp/'host.jsonl')])
 code=p.wait();sampler.wait(timeout=10)
import xml.etree.ElementTree as E
raw=(tmp/'full.xml').read_bytes();t=E.fromstring(raw)
r={'head':head,'tree':tree,'exit_code':code,'wall_seconds':time.time()-started,'suites':[s.attrib for s in t.findall('.//testsuite')],'testcases':len(t.findall('.//testcase')),'raw_junit_sha256':hashlib.sha256(raw).hexdigest(),'GC_or_threshold_changed':False}
(tmp/'full.xml.gz').write_bytes(gzip.compress(raw,mtime=0));(tmp/'full-state.json').write_text(json.dumps(r,indent=2))
for name in ('full.log','full.xml.gz','full-state.json','host.jsonl'):shutil.copy2(tmp/name,qa/('full-final-'+name if name=='host.jsonl' else name.replace('full','full-final',1)))
print(json.dumps(r),flush=True)
