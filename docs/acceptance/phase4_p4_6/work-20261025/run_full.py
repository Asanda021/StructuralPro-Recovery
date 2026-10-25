import subprocess,sys,os,time,json,gzip,hashlib
from pathlib import Path
out=Path(__file__).resolve().parent
tag=sys.argv[1] if len(sys.argv)>1 else 'full'
assert tag in ('full','full-final')
start=time.time();head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()
with (out/(tag+'.log')).open('w') as log:
 p=subprocess.Popen([sys.executable,'scripts/run_offline_tests.py','-q','--junitxml='+str(out/(tag+'.xml'))],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'})
 # /proc uses host PIDs although Popen.pid is in the nested namespace.
 for candidate in Path('/proc').iterdir():
  if not candidate.name.isdigit():continue
  try:
   command=(candidate/'cmdline').read_bytes()
   if b'scripts/run_offline_tests.py' in command and str(out/(tag+'.xml')).encode() in command:
    observed_pid=int(candidate.name);break
  except OSError:pass
 else:observed_pid=p.pid
 sampler=subprocess.Popen([sys.executable,'docs/acceptance/phase4_p4_6/verification-20261024/host-sampler.py',str(observed_pid),str(out/(tag+'-host.jsonl'))])
 code=p.wait();sampler.wait(timeout=10)
r={'head':head,'tree':tree,'exit_code':code,'wall_seconds':time.time()-start,'command':'python scripts/run_offline_tests.py -q --junitxml=full.xml','qt_platform':'offscreen','threshold_or_gc_changes':False}
if (out/(tag+'.xml')).exists():
 import xml.etree.ElementTree as ET
 t=ET.parse(out/(tag+'.xml'));r['suites']=[e.attrib for e in t.findall('.//testsuite')];r['testcases']=len(t.findall('.//testcase'));raw=(out/(tag+'.xml')).read_bytes();r['junit_sha256']=hashlib.sha256(raw).hexdigest();(out/(tag+'.xml.gz')).write_bytes(gzip.compress(raw,mtime=0))
(out/(tag+'-state.json')).write_text(json.dumps(r,indent=2));print(json.dumps(r))
