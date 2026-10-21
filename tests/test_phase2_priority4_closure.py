"""Synthetic CAD; real Qt/process/SQLite and independent numerical oracles."""
import math,json,hashlib,time
from pathlib import Path
import ezdxf,pytest
from core.drawings.dwg_takeoff import DWGTakeoffEngine

def fixture(tmp_path,n=1,unit=6):
 d=ezdxf.new('R2018');d.units=unit
 for i in range(n):d.modelspace().add_line((i,0),(i+3,4))
 p=tmp_path/f'{n}.dxf';d.saveas(p);return p

def qt():
 from PySide6.QtWidgets import QApplication
 global _q
 _q=QApplication.instance() or QApplication([]);return _q

def wait(fn):
 from PySide6.QtTest import QTest
 end=time.monotonic()+60
 while not fn() and time.monotonic()<end:QTest.qWait(10)
 assert fn()

def test_async_cancel_error_replace(tmp_path):
 from app.graphical_takeoff import GraphicalTakeoffDialog
 qt();p=fixture(tmp_path);large=fixture(tmp_path,10000);w=GraphicalTakeoffDialog(pdf_path=str(p));w.show()
 try:
  assert hasattr(w,'open_cad_async')
  w.open_cad_async(str(large));assert w.cad_loading and not w.commit_boq_button.isEnabled();w.cancel_cad_loading();assert w.viewer.path==p
  w.open_cad_async(str(large));w.open_cad_async(str(p));wait(lambda:not w.cad_loading);assert w.viewer.path==p
  bad=tmp_path/'bad.dxf';bad.write_text('broken');w.open_cad_async(str(bad));wait(lambda:not w.cad_loading);assert w.viewer.path==p and 'خطا' in w.status.text()
 finally:w.close()

@pytest.mark.parametrize('n',[10000,50000,100000])
def test_async_responsiveness_and_oracle(tmp_path,n):
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 qt();p=fixture(tmp_path,n);w=GraphicalTakeoffDialog();w.show();ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(10)
 try:
  start=time.monotonic();w.open_cad_async(str(p));wait(lambda:not w.cad_loading);elapsed=time.monotonic()-start
  assert w.viewer.path==p and len(w.cad_document.entities)==n
  assert sum(e.data['length'] for e in w.cad_document.entities)==5*n and len(w._cad_handle_items)==n
  assert len(ticks)>10;gap=max(b-a for a,b in zip(ticks,ticks[1:]));assert gap<.5
  QTest.mouseClick(w.fit,Qt.LeftButton);QTest.mouseClick(w.cad_layer_toggle,Qt.LeftButton);QTest.mouseClick(w.cad_layer_toggle,Qt.LeftButton)
  import resource
  (tmp_path/'responsiveness.json').write_text(json.dumps({'entities':n,'elapsed_s':elapsed,'timestamps':ticks,'max_event_gap_s':gap,'threshold_s':.5,'threshold_reason':'Coarse interactive 500ms upper bound on this shared Linux host; 10ms timer. Not a cross-machine SLA.','peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'oracle_m':n*5,'all_retained':True}))
  w.grab().save(str(tmp_path/'async-cad.png'))
 finally:timer.stop();w.close()

def test_array_supported_only_under_explicit_contract(tmp_path):
 d=ezdxf.new('R2018');d.units=6;b=d.blocks.new('B');b.add_line((0,0),(3,4));d.modelspace().add_blockref('B',(10,20),dxfattribs={'row_count':2,'column_count':3,'row_spacing':7,'column_spacing':9,'rotation':90});p=tmp_path/'array.dxf';d.saveas(p)
 assert hasattr(DWGTakeoffEngine,'with_array_support')
 doc=DWGTakeoffEngine.with_array_support().import_file(p);lines=[e for e in doc.entities if e.entity_type=='LINE'];assert len(lines)==6 and len({e.handle for e in lines})==6
 assert all('@' in e.handle for e in lines) and sum(e.data['length'] for e in lines)==pytest.approx(30)

def test_binary_dxf_explicit_rejection(tmp_path):
 p=tmp_path/'binary.dxf';p.write_bytes(b'AutoCAD Binary DXF\r\n\x1a\x00garbage')
 with pytest.raises(RuntimeError,match='Binary'):DWGTakeoffEngine().import_file(p)

def test_documented_unit_hash_and_oracle(tmp_path):
 from core.drawings import dwg_takeoff as cad
 p=fixture(tmp_path,unit=0);doc=DWGTakeoffEngine().import_file(p);assert hasattr(cad,'apply_documented_units')
 proof={'policy':'cad_unit_reference_v1','source_sha256':doc.source_sha256,'unit':'mm','reference_handle':doc.entities[0].handle,'cad_length':'5','real_length_m':'0.005','author':'author','reviewer':'other','reference':'Explicit synthetic 3-4-5 dimension'}
 f=tmp_path/'proof.json';f.write_text(json.dumps(proof));e={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 assert cad.apply_documented_units(doc,e).entities[0].data['length']==pytest.approx(.005)
 f.write_text('{}')
 with pytest.raises(ValueError):cad.apply_documented_units(doc,e)
