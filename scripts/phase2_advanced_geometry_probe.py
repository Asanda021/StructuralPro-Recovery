"""Transparent synthetic geometry/PDF performance and persistence receipt."""
from pathlib import Path
from hashlib import sha256
import json,math,time,resource,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz
from core.platform.application import StructuralProApp
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.graphical_takeoff import Point
from core.drawings.planar_geometry import regions_overlap
from core.drawings.pdf_engine import PDFDrawingEngine

def run(root):
 root.mkdir(parents=True,exist_ok=True);path=root/'synthetic-24-pages.pdf'
 with fitz.open() as pdf:
  for n in range(24):
   page=pdf.new_page(width=1200,height=900);shape=page.new_shape()
   for i in range(2000):
    x=10+i%400*2.5;y=10+i//400*120;shape.draw_line((x,y),(x+1,y+60))
   shape.finish(color=(0,0,0),width=.1);shape.commit()
  pdf.save(path)
 receipt={'synthetic':True,'engineering_approval':False,'pages':24,'pdf_bytes':path.stat().st_size,'source_sha256':sha256(path.read_bytes()).hexdigest(),'segments_per_page':2000}
 t=time.perf_counter();engine=PDFDrawingEngine(path);receipt['open_seconds']=time.perf_counter()-t;receipt['renders']=[]
 for page in (1,12,24):
  t=time.perf_counter();engine.render(page,150);receipt['renders'].append({'page':page,'seconds':time.perf_counter()-t})
 engine.close();app=StructuralProApp(root/'db');app.create_project('صرفاً آزمون مصنوعی هندسه','P')
 for floor in ('L1','L2'):app.add_project_floor('P',floor,level=floor)
 s=DrawingTakeoffSession(str(path));s.calibrate(1,100,1);s.calibrate(2,200,1)
 outer=[(500+300*math.cos(i*math.tau/64),500+300*math.sin(i*math.tau/64)) for i in range(64)]
 holes=[]
 for i in range(16):
  x=410+i%4*40;y=410+i//4*40;holes.append([Point(x,y),Point(x+10,y),Point(x+10,y+10),Point(x,y+10)])
 app.add_project_member('P','CURVE','L1','سطح مصنوعی')
 t=time.perf_counter();s.add_polygon([Point(*p) for p in outer],holes=holes,opening_refs=['SYNTHETIC O'+str(i) for i in range(16)],source='SYNTHETIC 64 VERTICES',floor_id='L1',member_id='CURVE',quantity_owner='explicit synthetic test owner')
 receipt['polygon_64_with_16_holes_seconds']=time.perf_counter()-t
 for i in range(20):
  x=100+i%5*100;y=100+i//5*100;member='G'+str(i);app.add_project_member('P',member,'L2','سطح مصنوعی')
  s.add_polygon([Point(x,y),Point(x+50,y),Point(x+50,y+50),Point(x,y+50)],page=2,source='SYNTHETIC '+member,floor_id='L2',member_id=member,quantity_owner='explicit synthetic owner '+member)
 t=time.perf_counter();saved=app.save_drawing_takeoff_session('P',s);receipt['save_seconds']=time.perf_counter()-t
 t=time.perf_counter();app.commit_drawing_takeoff_to_boq('P',saved['session_id'],[i.id for i in s.items],expected_session_revision=1);receipt['commit_21_regions_seconds']=time.perf_counter()-t
 previous=app.open_project('P');app.store.close();t=time.perf_counter();app=StructuralProApp(root/'db');assert app.open_project('P')==previous;receipt['reopen_seconds']=time.perf_counter()-t
 assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
 receipt.update(regions=21,outer_vertices=64,holes=16,boq_rows=len(previous['boq']),sqlite_integrity='ok',roundtrip_equal=True)
 app.store.close();t=time.perf_counter();assert regions_overlap(outer,[],[(x+2,y+2) for x,y in outer],[]);receipt['intersection_64_by_64_seconds']=time.perf_counter()-t
 receipt['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
 (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':run(Path(sys.argv[1]).resolve())
