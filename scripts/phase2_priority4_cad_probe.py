"""Synthetic DXF benchmark; timings are observations, never capacity promises."""
import sys,time,json,gc,resource,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def run(root,count):
 import ezdxf
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.graphical_takeoff import GraphicalTakeoffDialog
 root=Path(root);root.mkdir(parents=True,exist_ok=True);p=root/f'synthetic-{count}.dxf'
 d=ezdxf.new('R2018');d.header['$INSUNITS']=6
 for i in range(20):d.layers.new('سازه-'+str(i))
 m=d.modelspace()
 for i in range(count):
  x=(i%1000)*10;y=(i//1000)*10;m.add_line((x,y),(x+3,y+4),dxfattribs={'layer':'سازه-'+str(i%20)})
 d.saveas(p);del m,d;gc.collect()
 q=QApplication.instance() or QApplication([]);t=time.perf_counter();w=GraphicalTakeoffDialog(pdf_path=str(p));w.resize(1300,900);w.show();q.processEvents();elapsed=time.perf_counter()-t
 assert len(w.cad_document.entities)==count and sum(e.data['length'] for e in w.cad_document.entities)==count*5
 assert len(w._cad_handle_items)==count
 t=time.perf_counter();QTest.mouseClick(w.cad_layer_toggle,Qt.LeftButton);q.processEvents();toggle=time.perf_counter()-t
 t=time.perf_counter()
 for _ in range(10):w.canvas.scale_view(1.1);w.canvas.scale_view(1/1.1)
 q.processEvents();zoom=time.perf_counter()-t
 t=time.perf_counter();w.cad_handle.setText(w.cad_document.entities[-1].handle);QTest.mouseClick(w.cad_find,Qt.LeftButton);q.processEvents();find=time.perf_counter()-t
 w.grab().save(str(root/f'cad-{count}.png'));w.close();q.processEvents()
 r={'synthetic':True,'entity_count':count,'layers':20,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'open_parse_render_seconds':elapsed,'ui_blocking_load_seconds':elapsed,'toggle_layer_seconds':toggle,'twenty_zoom_operations_seconds':zoom,'indexed_handle_find_seconds':find,'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'oracle_total_length_m':count*5,'all_entities_retained':True,'oracle_match':True,'limitation':'Synchronous initial import/render; no background loading or unlimited-capacity claim.'}
 (root/f'benchmark-{count}.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
if __name__=='__main__':run(sys.argv[1],int(sys.argv[2]))
