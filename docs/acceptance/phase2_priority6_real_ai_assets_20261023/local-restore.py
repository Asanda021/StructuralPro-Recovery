from pathlib import Path
import zipfile,json,hashlib,subprocess,sys,os,tarfile,urllib.request,shutil
base=Path('/workspace/scratch/61dce18379e6');out=base/'p6-ai-local-restored';out.mkdir(exist_ok=True)
archive=base/'StructuralPro_P6_RealAI_1bff9740_20261023.compact.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='f111b655e44315803644d138e98024aba371f6e257f8936a78614115888871a7'
with zipfile.ZipFile(archive) as z:z.extractall(out)
m=json.loads((out/'MANIFEST.json').read_text())
for name,rec in m['files'].items():assert hashlib.sha256((out/name).read_bytes()).hexdigest()==rec['sha256'],name
subprocess.run(['git','clone',str(out/'code.bundle'),str(out/'repo')],check=True)
subprocess.run(['git','checkout','--detach',m['code_sha']],cwd=out/'repo',check=True)
subprocess.run(['git','fsck','--full'],cwd=out/'repo',check=True)
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=out/'repo',text=True).strip()==m['code_tree']
runtime=out/'runtime.tar.gz';runtime.write_bytes(urllib.request.urlopen(m['runtime_prerequisite']['url'],timeout=90).read())
assert hashlib.sha256(runtime.read_bytes()).hexdigest()==m['runtime_prerequisite']['sha256']
with tarfile.open(runtime) as t:t.extractall(out/'runtime',filter='data')
print('MANIFEST/Git/runtime PASS',flush=True)
# Relocate at source I/O only: signed stored paths and records remain unchanged.
original=base/'p6-ai-evidence';hold=base/'p6-ai-evidence-original-held';original.rename(hold);original.symlink_to(out/'evidence',target_is_directory=True)
try:
 sys.path.insert(0,str(out/'repo'))
 from core.platform.application import StructuralProApp
 results=[]
 for rel in ['sample','attempt2/sample','report-sample']:
  app=StructuralProApp(out/'evidence'/rel/'app');p=app.open_project('P');assert app.store.integrity_check()['ok'];results.append({'sample':rel,'boq_rows':len(p['boq']),'digest':app.store.current_digest('P')});app.store.close()
 env=dict(os.environ,PYTHONPATH=str(out/'repo'))
 subprocess.run([sys.executable,str(out/'repo/docs/acceptance/phase2_priority6_assets_20261023/report-readback.py'),str(out/'evidence/report-sample'),str(out/'report-readback.json')],env=env,cwd=out/'repo',check=True)
finally:original.unlink();hold.rename(original)
# Actual inference with the Standard bytes independently downloaded from Dropbox.
from core.ai.local_engine import LocalAIEngine
os.environ['STRUCTURALPRO_AI_RUNTIME_DIR']=str(out/'runtime/llama-b10549')
e=LocalAIEngine(model_dir=out/'models',model_path=base/'p6-ai-standard-restored.gguf',edition='standard',n_ctx=2048)
r=e.answer('The slab has no dimensions or thickness. State missing evidence. Do not invent numbers.')
assert r.source=='local-gguf' and r.requires_user_confirmation and not r.quantity_authority
result={'status':'LOCAL_RESTORE_PASS','dropbox_code_archive_restored':False,'reason':'Both new archive uploads rejected: INSUFFICIENT_SPACE','manifest_files':len(m['files']),'code_sha':m['code_sha'],'code_tree':m['code_tree'],'git_fsck':True,'sqlite':results,'runtime_reprovisioned_from_official_url':True,'standard_model_from_dropbox':True,'actual_restored_model_output':r.text,'provenance':r.provenance}
(out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
