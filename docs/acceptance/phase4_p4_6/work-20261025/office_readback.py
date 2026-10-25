from pathlib import Path
import subprocess,json,os
root=Path('/tmp/structuralpro-final-20261025');out=Path('/tmp/sp-all-office-20261025');out.mkdir(exist_ok=True)
r=[]
for fmt in ('docx','xlsx'):
 dest=out/fmt;dest.mkdir(exist_ok=True)
 files=sorted(root.rglob('*.'+fmt));assert len(files)==16
 with (dest/'convert.log').open('w') as log:
  p=subprocess.run(['/opt/codex/runtimes/codex-primary-runtime/dependencies/bin/override/soffice','--headless','-env:UserInstallation=file:///tmp/sp-lo-all-20261025','--convert-to','pdf','--outdir',str(dest),*[str(f) for f in files]],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 import fitz
 for f in files:
  target=dest/(f.stem+'.pdf');d=fitz.open(target);text='\n'.join(p.get_text() for p in d)
  r.append({'source':str(f.relative_to(root)),'engine':'LibreOffice; NOT Microsoft Office','pdf':str(target),'pages':len(d),'nonempty':bool(text.strip()),'formula_error_text':[x for x in ('#REF!','#DIV/0!','#VALUE!','#NAME?') if x in text]})
 assert p.returncode==0
Path('docs/acceptance/phase4_p4_6/work-20261025/office-readback.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps({'converted':len(r),'formula_errors':[x for x in r if x['formula_error_text']]}))
