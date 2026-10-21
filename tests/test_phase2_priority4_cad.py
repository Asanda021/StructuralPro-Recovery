"""Real ezdxf fixtures, explicit units, independent analytic oracles."""
import math
from pathlib import Path
import ezdxf,pytest
from core.drawings.dwg_takeoff import DWGTakeoffEngine

def drawing(tmp_path,unit=6):
 d=ezdxf.new('R2018');d.header['$INSUNITS']=unit;return d,tmp_path/'نقشه.dxf'
def read(d,p):d.saveas(p);return DWGTakeoffEngine().import_file(p)

@pytest.mark.parametrize('unit,length',[(6,5),(4,.005),(5,.05),(1,.127),(2,1.524)])
def test_unit_oracle(tmp_path,unit,length):
 d,p=drawing(tmp_path,unit);d.modelspace().add_line((0,0),(3,4));e=read(d,p).entities[0];assert e.data['length']==pytest.approx(length,rel=1e-12)

@pytest.mark.parametrize('kind',['LINE','POLYLINE','CIRCLE'])
def test_nonplanar_geometry_never_becomes_2d_quantity(tmp_path,kind):
 d,p=drawing(tmp_path);m=d.modelspace()
 if kind=='LINE':m.add_line((0,0,0),(3,4,12))
 elif kind=='POLYLINE':m.add_polyline3d([(0,0,0),(3,0,1),(3,3,2)])
 else:m.add_circle((0,0,2),1)
 doc=read(d,p)
 with pytest.raises(ValueError):DWGTakeoffEngine().layer_takeoff(doc,{'0':{'metric':'length'}})

@pytest.mark.parametrize('mirror',[1,-1])
def test_nested_block_transform_and_identity(tmp_path,mirror):
 d,p=drawing(tmp_path);b=d.blocks.new('leaf');leaf=b.add_line((0,0),(3,4));outer=d.blocks.new('outer');outer.add_blockref('leaf',(2,0),dxfattribs={'xscale':2,'yscale':2});root=d.modelspace().add_blockref('outer',(10,20),dxfattribs={'rotation':90,'xscale':mirror,'yscale':1})
 doc=read(d,p);lines=[e for e in doc.entities if e.entity_type=='LINE'];assert len(lines)==1
 e=lines[0];assert e.data['length']==pytest.approx(10);assert e.handle.startswith(root.dxf.handle+'/') and leaf.dxf.handle in e.handle
 assert e.data['start']==pytest.approx((10,20+2*mirror))

def test_cyclic_block_fails_closed(tmp_path):
 d,p=drawing(tmp_path);b=d.blocks.new('loop');b.add_blockref('loop',(0,0));d.modelspace().add_blockref('loop',(0,0))
 with pytest.raises(RuntimeError):read(d,p)

def test_large_coordinate_small_area_is_not_lost(tmp_path):
 d,p=drawing(tmp_path);n=10**12;d.modelspace().add_lwpolyline([(n,n),(n+1,n),(n+1,n+1),(n,n+1)],close=True)
 assert read(d,p).entities[0].data['area']==1

@pytest.mark.parametrize('kind',['CIRCLE','ARC'])
def test_curves_analytic_oracle(tmp_path,kind):
 d,p=drawing(tmp_path);m=d.modelspace()
 if kind=='CIRCLE':m.add_circle((0,0),2)
 else:m.add_arc((0,0),2,0,90)
 assert read(d,p).entities[0].data['length']==pytest.approx(4*math.pi if kind=='CIRCLE' else math.pi,rel=1e-12)

def test_hidden_layer_and_parent_plus_child_do_not_authorize_quantities(tmp_path):
 d,p=drawing(tmp_path);d.layers.new('hidden');d.layers.get('hidden').off();d.modelspace().add_line((0,0),(1,0),dxfattribs={'layer':'hidden'});doc=read(d,p)
 with pytest.raises(ValueError):DWGTakeoffEngine().layer_takeoff(doc,{'hidden':{'metric':'length'}})
 d,p=drawing(tmp_path);b=d.blocks.new('B');b.add_line((0,0),(1,0));d.modelspace().add_blockref('B',(0,0));doc=read(d,p)
 with pytest.raises(ValueError):DWGTakeoffEngine().layer_takeoff(doc,{'0':{'metric':'count'}})

def test_native_layer_controls_and_handle_selection(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.graphical_takeoff import GraphicalTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([])
 d,p=drawing(tmp_path);d.layers.new('سازه');line=d.modelspace().add_line((0,0),(3,4),dxfattribs={'layer':'سازه'});d.modelspace().add_text('ستون C1 — ۱۲',dxfattribs={'insert':(1,1),'height':.5,'layer':'سازه'});d.saveas(p)
 w=GraphicalTakeoffDialog(pdf_path=str(p));w.resize(1300,900);w.show();_qt.processEvents()
 try:
  assert hasattr(w,'cad_layers')
  w.cad_layers.setCurrentIndex(w.cad_layers.findData('سازه'));QTest.mouseClick(w.cad_layer_toggle,Qt.LeftButton)
  assert not any(i.isVisible() for i in w._cad_items['سازه'])
  QTest.mouseClick(w.cad_layer_toggle,Qt.LeftButton);assert all(i.isVisible() for i in w._cad_items['سازه'])
  QTest.keyClicks(w.cad_handle,line.dxf.handle);QTest.mouseClick(w.cad_find,Qt.LeftButton)
  assert len(w.canvas.scene.selectedItems())==1 and line.dxf.handle in w.status.text()
  before=[e.data for e in w.cad_document.entities];QTest.mouseClick(w.fit,Qt.LeftButton);assert before==[e.data for e in w.cad_document.entities]
  w.grab().save(str(tmp_path/'cad-rtl.png'))
 finally:w.close()

@pytest.mark.parametrize('fault',['timeout','source_change'])
def test_offline_converter_failures_reject_untrusted_artifact(tmp_path,monkeypatch,fault):
 import subprocess
 from core.drawings.dwg_converter import OfflineDWGConverter,DWGConversionError
 source=tmp_path/'منبع.dwg';source.write_bytes(b'AC1032-boundary-only-not-a-real-dwg')
 def run(command,**kwargs):
  if fault=='timeout':raise subprocess.TimeoutExpired(command,1)
  d,_=drawing(tmp_path);d.modelspace().add_line((0,0),(1,0));d.saveas(command[2]);source.write_bytes(b'AC1032-modified-during-conversion')
  return subprocess.CompletedProcess(command,0,'','')
 monkeypatch.setattr('core.drawings.dwg_converter.subprocess.run',run)
 with pytest.raises(DWGConversionError):OfflineDWGConverter('boundary-only').convert(source,tmp_path/'output')

def test_unknown_cad_units_cannot_enter_boq(tmp_path):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from core.drawings.graphical_takeoff import Point
 d,p=drawing(tmp_path,0);d.modelspace().add_line((0,0),(3,4));d.saveas(p)
 app=StructuralProApp(tmp_path/'db');app.create_project('واحد مجهول','P');s=DrawingTakeoffSession(str(p));s.calibrate(1,1,1);i=s.add_length([Point(0,0),Point(3,4)],takeoff_code='line',source='explicit-test')
 r=app.save_drawing_takeoff_session('P',s);before=app.open_project('P')
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 assert app.open_project('P')==before;app.store.close()

def test_existing_manual_cad_measurement_sqlite_cas_boq_and_source_change(tmp_path):
 from copy import deepcopy
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from core.drawings.graphical_takeoff import Point
 d,p=drawing(tmp_path,6);d.modelspace().add_line((0,0),(3,4));d.saveas(p)
 app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی؛ طراحی واقعی نیست','P');app.add_project_floor('P','طبقه صریح',level='L1');app.add_project_member('P','M1','L1','تیر')
 def measure():
  s=DrawingTakeoffSession(str(p));s.calibrate(1,1,1);i=s.add_length([Point(0,0),Point(3,4)],takeoff_code='line',source='explicit CAD manual reference / independent 5 m oracle');return s,i
 s,i=measure();r=app.save_drawing_takeoff_session('P',s);app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 original=deepcopy(app.open_project('P'));assert original['boq'][0]['quantity']==5
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')==original
 t,j=measure();rr=app.save_drawing_takeoff_session('P',t);before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rr['session_id'],[j.id],expected_session_revision=1)
 assert app.open_project('P')==before
 with pytest.raises(RuntimeError):app.save_drawing_takeoff_session('P',t,session_id=rr['session_id'],expected_revision=0)
 assert app.open_project('P')==before
 p.write_bytes(p.read_bytes()+b'\n')
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rr['session_id'],[j.id],expected_session_revision=1)
 assert app.open_project('P')==before and app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';app.store.close()

def test_duplicate_raw_handle_is_not_silently_repaired(tmp_path):
 d,p=drawing(tmp_path);a=d.modelspace().add_line((0,0),(1,0));b=d.modelspace().add_line((0,2),(1,2));d.saveas(p)
 text=p.read_text();needle='  5\n'+b.dxf.handle+'\n';assert needle in text;p.write_text(text.replace(needle,'  5\n'+a.dxf.handle+'\n',1))
 with pytest.raises(RuntimeError):DWGTakeoffEngine().import_file(p)

def test_2d_polyline_elevation_and_text_rotation_are_explicit(tmp_path):
 d,p=drawing(tmp_path);d.modelspace().add_polyline2d([(0,0),(3,4)],dxfattribs={'elevation':(0,0,2)});d.modelspace().add_text('ستون',dxfattribs={'rotation':30,'height':1})
 doc=read(d,p);assert doc.entities[0].data.get('unsupported_measurement');assert doc.entities[1].data['rotation']==30;assert 'font_name' in doc.entities[1].data
