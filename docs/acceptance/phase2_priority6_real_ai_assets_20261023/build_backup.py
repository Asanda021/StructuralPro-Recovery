from pathlib import Path
import json,hashlib,zipfile,sys
root=Path('/workspace/scratch/61dce18379e6');ev=root/'p6-ai-evidence';assets=root/'p6-ai-assets'
assert (ev/'full.exit').read_text().strip()=='0'
files={'code.bundle':ev/'code.bundle','runtime/llama-b10549-bin-ubuntu-x64.tar.gz':assets/'llama-b10549-bin-ubuntu-x64.tar.gz'}
for f in ev.rglob('*'):
 if f.is_file() and '__pycache__' not in f.parts:files['evidence/'+str(f.relative_to(ev))]=f
manifest={'code_sha':'1bff974083cdfaff892c037139191fc31c35b65d','code_tree':'a16fa8f5f61bb4b5f7953488a8468e32bd4221cc','original_evidence_root':str(ev),'models':json.loads((ev/'downloads.json').read_text()),'standard_dropbox_id':'id:npSmebsorqwAAAAAAAAAwA','model_weights_embedded':False,'vision_prerequisite':'Provision exact pinned GGUF/projector from official URLs; evaluation under Qwen Research License. Not a commercial distribution approval.','files':{k:{'bytes':v.stat().st_size,'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for k,v in files.items()}}
p=root/'StructuralPro_P6_RealAI_1bff9740_20261023.zip'
with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for k,v in files.items():z.write(v,k)
 z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
meta={'file':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'manifest_files':len(files)}
(root/'p6-ai-backup.json').write_text(json.dumps(meta,indent=2));print(json.dumps(meta))
