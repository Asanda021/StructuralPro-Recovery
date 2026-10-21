from pathlib import Path
import time,json,resource,hashlib
import fitz
from core.drawings.pdf_engine import PDFDrawingEngine
root=Path('/tmp/p3-evidence/large');root.mkdir(exist_ok=True);path=root/'synthetic-large.pdf'
with fitz.open() as pdf:
 for page_number in range(24):
  p=pdf.new_page(width=1200,height=900);s=p.new_shape()
  for i in range(40000):
   x=10+(i%1000)*1.17;y=10+(i//1000)*21.5;s.draw_line((x,y),(x+.5,y+10))
  s.finish(color=(0,0,0),width=.1);s.commit()
 pdf.save(path,deflate=False)
r={'synthetic':True,'engineering_approval':False,'pages':24,'segments_per_page':40000,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
t=time.perf_counter();e=PDFDrawingEngine(path);r['open_seconds']=time.perf_counter()-t;r['renders']=[]
for page in (1,12,24):
 t=time.perf_counter();e.render(page,150);r['renders'].append({'page':page,'seconds':time.perf_counter()-t})
e.close();r['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
(root/'receipt.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
