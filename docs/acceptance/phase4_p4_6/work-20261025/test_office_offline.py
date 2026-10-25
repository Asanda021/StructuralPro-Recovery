"""Real LibreOffice conversions under inherited native-network denial."""
from pathlib import Path
import subprocess,json

def test_all_office_files_reopen_and_print_offline():
 root=Path('/tmp/structuralpro-final-20261025');out=Path('/tmp/sp-office-offline-20261025');out.mkdir(exist_ok=True);results=[]
 for fmt in ('docx','xlsx'):
  dest=out/fmt;dest.mkdir(exist_ok=True)
  for n,p in enumerate(sorted(root.rglob('*.'+fmt))):
   profile=f'file:///tmp/sp-offline-profile-{fmt}-{n}-20261025'
   with (dest/(p.stem+'.log')).open('w') as log:
    run=subprocess.run(['/opt/codex/runtimes/codex-primary-runtime/dependencies/bin/override/soffice','--headless','-env:UserInstallation='+profile,'--convert-to','pdf','--outdir',str(dest),str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=30)
   assert run.returncode==0
   import fitz
   target=dest/(p.stem+'.pdf')
   with fitz.open(target) as d:
    text='\n'.join(page.get_text() for page in d)
    row={'source':str(p.relative_to(root)),'engine':'LibreOffice offline; NOT Microsoft Office','pdf':str(target),'pages':len(d),'nonempty':bool(text.strip()),'formula_error_text':[x for x in ('#REF!','#DIV/0!','#VALUE!','#NAME?') if x in text]}
    assert row['nonempty'] and not row['formula_error_text'];results.append(row)
    Path('docs/acceptance/phase4_p4_6/work-20261025/office-offline.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 assert len(results)==32
