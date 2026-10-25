"""Read all fresh exports and render real Office files with native networking denied."""
from pathlib import Path
import subprocess,json,runpy,sys

def test_fresh_readback_and_office_print():
 root=Path('/tmp/sp-sqlite-closure-20261025-frozen/original-tmp-scenario');out=Path('/tmp/sp-closure-render-20261025');out.mkdir(exist_ok=False)
 qa=Path('docs/acceptance/phase4_p4_6/closure-20261025').resolve()
 # Existing readback contract checks the exact64-file set, RTL, Jalali and tables.
 old=sys.argv;sys.argv=['readback.py',str(root),str(qa/'readback.json')]
 try:runpy.run_path('docs/acceptance/phase4_p4_6/verification-20261024/readback.py',run_name='__main__')
 finally:sys.argv=old
 import openpyxl,fitz
 for p in root.rglob('*.xlsx'):
  w=openpyxl.load_workbook(p);s=w['خلاصه'];assert s.max_row>=4
  assert any(c.value not in (None,'') for row in s.iter_rows(min_row=4) for c in row)
 records=[]
 for fmt in ('docx','xlsx'):
  dest=out/fmt;dest.mkdir()
  for n,p in enumerate(sorted(root.rglob('*.'+fmt))):
   with (dest/(p.stem+'.log')).open('w') as log:
    command=['/opt/codex/runtimes/codex-primary-runtime/dependencies/bin/override/soffice','--headless','-env:UserInstallation=file:///tmp/sp-closure-office-'+fmt+'-'+str(n),'--convert-to','pdf','--outdir',str(dest),str(p)]
    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=45);assert result.returncode==0
   with fitz.open(dest/(p.stem+'.pdf')) as d:
    text='\n'.join(page.get_text() for page in d);assert text.strip()
    assert not any(x in text for x in ('#REF!','#DIV/0!','#VALUE!','#NAME?'))
    if fmt=='docx' and p.stem in ('dashboard','package'):assert len(d)<=15
    records.append({'file':str(p.relative_to(root)),'rendered_pdf':str(dest/(p.stem+'.pdf')),'pages':len(d),'engine':'LibreOffice offline; NOT Microsoft Office'})
    (qa/'office-render.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
 assert len(records)==32
 for kind in ('dashboard','package'):
  with (out/(kind+'-official.log')).open('w') as log:
   command=['/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3','/root/.codex/skills/builtins/documents/render_docx.py',str(root/(kind+'.docx')),'--output_dir',str(out/('official-'+kind)),'--emit_pdf']
   subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=60)
