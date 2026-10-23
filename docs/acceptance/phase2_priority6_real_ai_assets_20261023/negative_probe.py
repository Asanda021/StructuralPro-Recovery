import os,json,subprocess,sys,dataclasses
from pathlib import Path
root=Path('/workspace/scratch/61dce18379e6/p6-ai-real');sys.path.insert(0,str(root))
from core.ai.local_engine import LocalAIEngine
from core.platform.application import StructuralProApp
out=root.parent/'p6-ai-evidence';assets=root.parent/'p6-ai-assets'
os.environ['STRUCTURALPRO_AI_RUNTIME_DIR']=str(assets/'runtime-linux/llama-b10549');os.environ['STRUCTURALPRO_AI_MODEL_DIR']=str(assets)
app=StructuralProApp(out/'attempt2/sample/app');before=app.store.current_digest('P');boq=app.open_project('P')['boq'];records=[];realrun=subprocess.run;commands=[]
def record(argv,**kwargs):
 try:
  r=realrun(argv,**kwargs);commands.append({'argv':argv,'exit_code':r.returncode,'stderr':r.stderr});return r
 except subprocess.TimeoutExpired:
  commands.append({'argv':argv,'timeout_seconds':kwargs.get('timeout'),'actual_process_timeout':True});raise
subprocess.run=record
bad=out/'explicit-invalid.gguf';bad.write_bytes(b'This is an INVALID model fixture, never a valid GGUF.')
e=LocalAIEngine(model_path=bad,edition='standard');r=e.answer('Explain source review');assert r.source!='local-gguf';records.append({'scenario':'invalid_gguf_real_runtime','response':dataclasses.asdict(r),'error':e._load_error})
def timeout(argv,**kwargs):
 kwargs['timeout']=.001;return record(argv,**kwargs)
subprocess.run=timeout
e=LocalAIEngine(edition='standard');r=e.answer('Explain source review');assert r.source!='local-gguf';records.append({'scenario':'actual_runtime_timeout_1ms','response':dataclasses.asdict(r),'error':e._load_error})
subprocess.run=record
e=LocalAIEngine(edition='light');r=e.answer('Explain source review');assert r.source=='fail-closed';records.append({'scenario':'light_with_assets_no_execution','response':dataclasses.asdict(r)})
assert len(commands)==2 and app.store.current_digest('P')==before and app.open_project('P')['boq']==boq
assert app.store.integrity_check()['ok'];app.store.close()
(out/'negative-results.json').write_text(json.dumps({'scenarios':records,'commands':commands,'boq_unchanged':True,'digest':before,'status':'PASS'},ensure_ascii=False,indent=2));print('3 real-process/edition negative scenarios PASS')
