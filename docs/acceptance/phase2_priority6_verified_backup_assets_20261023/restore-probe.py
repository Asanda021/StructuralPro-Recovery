from pathlib import Path
import sys,json,hashlib,zipfile,subprocess,tarfile,urllib.request,os,dataclasses,time
base=Path('/workspace/scratch/61dce18379e6');mode=sys.argv[1];root=base/'p6-verified-close';dest=root/mode;dest.mkdir(exist_ok=True)
expected={'full':('10d09f3168e67a6d95ae867bfe7ff3e166125d8adacc8640ee41782d4ab58995',41865320),'compact':('f111b655e44315803644d138e98024aba371f6e257f8936a78614115888871a7',13144105)}[mode]
p=root/(mode+'-from-dropbox.zip');assert p.stat().st_size==expected[1] and hashlib.sha256(p.read_bytes()).hexdigest()==expected[0]
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 z.extractall(dest)
m=json.loads((dest/'MANIFEST.json').read_text())
for name,rec in m['files'].items():
 f=dest/name;assert f.stat().st_size==rec['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==rec['sha256'],name
subprocess.run(['git','clone',str(dest/'code.bundle'),str(dest/'repo')],check=True)
subprocess.run(['git','checkout','--detach',m['code_sha']],cwd=dest/'repo',check=True)
subprocess.run(['git','fsck','--full'],cwd=dest/'repo',check=True)
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=dest/'repo',text=True).strip()==m['code_tree']
if mode=='full':runtime=dest/'runtime/llama-b10549-bin-ubuntu-x64.tar.gz'
else:
 runtime=dest/'runtime.tar.gz';runtime.write_bytes(urllib.request.urlopen(m['runtime_prerequisite']['url'],timeout=120).read())
assert hashlib.sha256(runtime.read_bytes()).hexdigest()=='66b26d8cb3ab8edaf5a12bfe642b8f00844925f614f196a96a222b7ed1582c1d'
with tarfile.open(runtime) as t:t.extractall(dest/'runtime-unpacked',filter='data')
original=base/'p6-ai-evidence';held=base/('p6-evidence-held-'+mode);original.rename(held);original.symlink_to(dest/'evidence',target_is_directory=True)
sys.path.insert(0,str(dest/'repo'));sql=[]
try:
 from core.platform.application import StructuralProApp
 for rel in ['sample','attempt2/sample','report-sample']:
  app=StructuralProApp(dest/'evidence'/rel/'app');project=app.open_project('P');before=app.store.current_digest('P');assert app.store.integrity_check()['ok']
  display=[]
  for review in project.get('ifc_identity_reviews',[]):
   proposal_id=review.get('proposal_id')
   if proposal_id:
    geometry=app.ifc_display_geometry('P',proposal_id);assert geometry['quantity_authority'] is False if 'quantity_authority' in geometry else geometry['financial_permission'] is False
    display.append(proposal_id)
  assert app.store.current_digest('P')==before
  sql.append({'sample':rel,'digest':before,'boq_rows':len(project['boq']),'ifc_display_checked':len(display)})
  app.store.close()
 subprocess.run([sys.executable,str(dest/'repo/docs/acceptance/phase2_priority6_assets_20261023/report-readback.py'),str(dest/'evidence/report-sample'),str(dest/'report-readback.json')],cwd=dest/'repo',env=dict(os.environ,PYTHONPATH=str(dest/'repo')),check=True)
finally:original.unlink();held.rename(original)
# The model is a pinned external prerequisite, never embedded in the code bundle.
assets=base/'p6-ai-assets'
from core.ai.local_engine import LocalAIEngine
os.environ['STRUCTURALPRO_AI_RUNTIME_DIR']=str(dest/'runtime-unpacked/llama-b10549')
responses=[]
for edition in ['standard','pro']:
 e=LocalAIEngine(model_dir=assets,model_path=base/'p6-delete-verified.gguf' if edition=='standard' else None,edition=edition,n_ctx=4096)
 t=time.monotonic();r=e.answer('Which documents are missing for a slab without dimensions or thickness? Do not invent values.') if edition=='standard' else e.answer_with_image(dest/'evidence/attempt2/plan.png','Describe visible boundaries. No dimensions are documented. Suggestions only, one short paragraph.')
 assert r.source==('local-gguf' if edition=='standard' else 'local-gguf-vision') and r.requires_user_confirmation and not r.quantity_authority
 responses.append({'edition':edition,'seconds':time.monotonic()-t,'response':dataclasses.asdict(r)})
result={'status':'PASS','mode':mode,'archive_from_dropbox':True,'archive_sha256':expected[0],'archive_bytes':expected[1],'manifest_files':len(m['files']),'code_sha':m['code_sha'],'code_tree':m['code_tree'],'git_fsck':True,'sqlite':sql,'actual_inference':responses,'runtime':('restored from archive' if mode=='full' else 'reprovisioned from official pinned URL'),'gguf_assets':'External pinned prerequisites, SHA verified by previous download and actual response provenance; Standard bytes freshly downloaded from Dropbox before authorized deletion.'}
(dest/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
