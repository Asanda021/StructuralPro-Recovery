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
 s,i=measure();r=app.save_drawing_takeoff_session('P',s)
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 original=deepcopy(app.open_project('P'));assert original['boq']==[] and s.items[0].quantity==5
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')==original
 t,j=measure();rr=app.save_drawing_takeoff_session('P',t);before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rr['session_id'],[j.id],expected_session_revision=1)
 assert app.open_project('P')==before
 with pytest.raises(RuntimeError):app.save_drawing_takeoff_session('P',t,session_id=rr['session_id'],expected_revision=0)
 assert app.open_project('P')==before
 p.write_bytes(p.read_bytes()+b'\n')
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rr['session_id'],[j.id],expected_session_revision=1)
 assert app.open_project('P')==before and app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';app.store.close()

@pytest.mark.parametrize('alias',['same','lowercase','leading_zero'])
def test_duplicate_raw_handle_is_not_silently_repaired(tmp_path,alias):
 d,p=drawing(tmp_path);a=d.modelspace().add_line((0,0),(1,0));b=d.modelspace().add_line((0,2),(1,2));d.saveas(p)
 text=p.read_text();needle='  5\n'+b.dxf.handle+'\n';assert needle in text;replacement=a.dxf.handle if alias=='same' else a.dxf.handle.lower() if alias=='lowercase' else '00'+a.dxf.handle;p.write_text(text.replace(needle,'  5\n'+replacement+'\n',1))
 with pytest.raises(RuntimeError):DWGTakeoffEngine().import_file(p)

def test_2d_polyline_elevation_and_text_rotation_are_explicit(tmp_path):
 d,p=drawing(tmp_path);d.modelspace().add_polyline2d([(0,0),(3,4)],dxfattribs={'elevation':(0,0,2)});d.modelspace().add_text('ستون',dxfattribs={'rotation':30,'height':1})
 doc=read(d,p);assert doc.entities[0].data.get('unsupported_measurement');assert doc.entities[1].data['rotation']==30;assert 'font_name' in doc.entities[1].data

@pytest.mark.parametrize('metric,expected',[('length',5),('area',12)])
def test_entity_binding_review_and_boq_are_real(tmp_path,metric,expected):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from copy import deepcopy
 d,p=drawing(tmp_path);m=d.modelspace();e=m.add_line((0,0),(3,4)) if metric=='length' else m.add_lwpolyline([(0,0),(4,0),(4,3),(0,3)],close=True);d.saveas(p);doc=DWGTakeoffEngine().import_file(p)
 app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی CAD','P');app.add_project_floor('P','طبقه',level='L1');app.add_project_member('P','M1','L1','عضو صریح')
 s=DrawingTakeoffSession(str(p));item=s.add_cad_entity(doc,e.dxf.handle,metric,takeoff_code='cad-item',floor_id='L1',member_id='M1',quantity_owner='explicit synthetic claim',created_by='author',reference='synthetic independent CAD dimensions')
 r=app.save_drawing_takeoff_session('P',s);before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 assert app.open_project('P')==before
 with pytest.raises(ValueError):s.review_cad_entity(item.id,reviewer='author',note='self review')
 s.review_cad_entity(item.id,reviewer='independent reviewer',note='explicit analytical oracle');r=app.save_drawing_takeoff_session('P',s,session_id=r['session_id'],expected_revision=1)
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=2)
 final=deepcopy(app.open_project('P'));assert final['boq'][0]['quantity']==expected;assert final['takeoffs'][0]['params']['cad_evidence']['handle']==e.dxf.handle
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')==final;app.store.close()

def test_native_entity_to_review_sqlite_boq_buttons(tmp_path):
 from PySide6.QtWidgets import QApplication,QInputDialog,QDialogButtonBox,QMessageBox
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.graphical_takeoff import GraphicalTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([])
 d,p=drawing(tmp_path);e=d.modelspace().add_line((0,0),(3,4));d.saveas(p)
 app=StructuralProApp(tmp_path/'db');app.create_project('CAD مصنوعی','P');app.add_project_floor('P','طبقه',level='L1');app.add_project_member('P','M1','L1','عضو')
 w=GraphicalTakeoffDialog(pdf_path=str(p),app_service=app,project_id='P');w.resize(1500,1100);w.show();_qt.processEvents();errors=[]
 def answers(values):
  queue=list(values)
  def respond():
   modal=_qt.activeModalWidget()
   try:
    assert isinstance(modal,QInputDialog);modal.setTextValue(queue.pop(0))
    if queue:QTimer.singleShot(20,respond)
    QTest.mouseClick(modal.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
   except Exception as exc:
    errors.append(str(exc))
    if modal:modal.reject()
  QTimer.singleShot(20,respond)
 try:
  assert hasattr(w,'cad_measure') and hasattr(w,'cad_review')
  w.polygon_floor.setText('L1');w.polygon_member.setText('M1');w.polygon_owner.setText('explicit synthetic sole claim')
  w.cad_handle.setText(e.dxf.handle);QTest.mouseClick(w.cad_find,Qt.LeftButton)
  answers(['cad-line','author','explicit synthetic drawing']);QTest.mouseClick(w.cad_measure,Qt.LeftButton);assert not errors and len(w.session.items)==1
  QTest.mouseClick(w.table.viewport(),Qt.LeftButton,pos=w.table.visualItemRect(w.table.item(0,0)).center())
  answers(['independent reviewer','5 m analytic oracle']);QTest.mouseClick(w.cad_review,Qt.LeftButton);assert not errors and w.session.items[0].cad_evidence['review']
  QTest.mouseClick(w.save_session_button,Qt.LeftButton)
  def confirm():
   m=_qt.activeModalWidget();assert isinstance(m,QMessageBox);QTest.mouseClick(m.button(QMessageBox.Yes),Qt.LeftButton)
  QTimer.singleShot(20,confirm);QTest.mouseClick(w.commit_boq_button,Qt.LeftButton);assert app.open_project('P')['boq'][0]['quantity']==5
  w.grab().save(str(tmp_path/'cad-entity-review-boq.png'))
 finally:w.close();app.store.close()

@pytest.mark.parametrize('fault',['review','geometry','handle','owner','unit','calibration','missing_member','financial','duplicate'])
def test_cad_binding_failures_preserve_sqlite_and_boq(tmp_path,fault):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from copy import deepcopy
 from dataclasses import replace
 d,p=drawing(tmp_path);entity=d.modelspace().add_line((0,0),(3,4));d.saveas(p);doc=read(d,p)
 app=StructuralProApp(tmp_path/'db');app.create_project('آزمون منفی CAD','P');app.add_project_floor('P','طبقه',level='L1');app.add_project_member('P','M1','L1','عضو')
 s=DrawingTakeoffSession(str(p));i=s.add_cad_entity(doc,entity.dxf.handle,'length',takeoff_code='cad-item',floor_id='L1',member_id='M1',quantity_owner='claim',created_by='author',reference='explicit synthetic oracle');s.review_cad_entity(i.id,reviewer='other',note='5 m')
 if fault=='duplicate':
  r=app.save_drawing_takeoff_session('P',s);app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
  history=deepcopy(app.open_project('P'));bad=deepcopy(history);bad['takeoffs'][0]['quantities'][0]['amount']=6
  with pytest.raises(ValueError):app.store.save('P',bad)
  assert app.open_project('P')==history
  s=DrawingTakeoffSession(str(p));i=s.add_cad_entity(doc,entity.dxf.handle,'length',takeoff_code='cad-item',floor_id='L1',member_id='M1',quantity_owner='renamed claim',created_by='author',reference='same part with shifted display',scene_origin=(100,100));s.review_cad_entity(i.id,reviewer='other',note='5 m')
 else:
  item=s.find(i.id);meta=deepcopy(item.cad_evidence)
  if fault=='review':meta['review']['reviewer']='author'
  if fault=='geometry':meta['scene_origin']=[1,1]
  if fault=='handle':meta['handle']='MISSING'
  if fault=='owner':meta['quantity_owner']='changed after review'
  if fault=='unit':meta['unit_basis']='mm'
  if fault=='missing_member':meta['member_id']='UNKNOWN'
  s.items[0]=replace(item,cad_evidence=meta)
  if fault=='calibration':
   before=deepcopy(app.open_project('P'))
   with pytest.raises(ValueError):s.calibrate(1,1,2)
   assert app.open_project('P')==before;app.store.close();return
  if fault=='financial':
   project=app.open_project('P');project['contract']={'id':'locked contract'};app.store.save('P',project)
 if fault=='calibration':
  before=deepcopy(app.open_project('P'))
  with pytest.raises(ValueError):app.save_drawing_takeoff_session('P',s)
 else:
  r=app.save_drawing_takeoff_session('P',s);before=deepcopy(app.open_project('P'))
  with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 assert app.open_project('P')==before;app.store.close()

def test_bridge_version_capability_is_explicit(tmp_path,monkeypatch):
 import subprocess
 from core.cad.external_dwg_provider_v1 import ACadSharpDWGProvider,DWGConverterConfig
 p=tmp_path/'bridge';p.write_text('boundary-only')
 monkeypatch.setattr('core.cad.external_dwg_provider_v1.subprocess.run',lambda *a,**k:subprocess.CompletedProcess(a[0],0,'ACadSharp 3.8.0.0',''))
 assert ACadSharpDWGProvider(DWGConverterConfig(str(p))).version=='3.8.0.0'

def test_cad_polygon_revision_keeps_new_handle_provenance_and_old_history(tmp_path):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from copy import deepcopy
 from hashlib import sha256
 import json
 app=StructuralProApp(tmp_path/'db');app.create_project('اصلاحیه CAD مصنوعی','P');app.add_project_floor('P','طبقه',level='L1');app.add_project_member('P','M1','L1','عضو')
 def measured(name,width):
  d=ezdxf.new('R2018');d.header['$INSUNITS']=6;e=d.modelspace().add_lwpolyline([(0,0),(width,0),(width,3),(0,3)],close=True);p=tmp_path/name;d.saveas(p);doc=DWGTakeoffEngine().import_file(p);s=DrawingTakeoffSession(str(p));i=s.add_cad_entity(doc,e.dxf.handle,'area',takeoff_code='cad-area',floor_id='L1',member_id='M1',quantity_owner='claim',created_by='author',reference='explicit synthetic revision');s.review_cad_entity(i.id,reviewer='other',note='width times 3 m');return s,i
 s,i=measured('original.dxf',4);r=app.save_drawing_takeoff_session('P',s);app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1);original=deepcopy(app.open_project('P'));key=original['takeoffs'][0]['source_id']
 newer,j=measured('revised.dxf',5);doc=app.drawing_amendment_document('P',key,newer.to_dict(),expected_revision=1,expected_session_revision=2);p=tmp_path/'revision.json';p.write_text(json.dumps(doc))
 a=app.create_drawing_amendment('P',key,newer.to_dict(),expected_revision=1,expected_session_revision=2,created_by='author',reason='explicit width 4 to 5 m',evidence={'evidence_path':str(p),'evidence_sha256':sha256(p.read_bytes()).hexdigest(),'evidence_reference':'synthetic revision'})
 assert a['rows'][0]['params']['cad_evidence']['source_sha256']==newer.source_sha256
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='15 m2 oracle');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 final=app.open_project('P');assert final['takeoffs']==original['takeoffs'] and final['boq'][0]['quantity']==15;app.store.close()

def test_array_insert_is_not_silently_reduced_to_one_instance(tmp_path):
 d,p=drawing(tmp_path);b=d.blocks.new('B');b.add_line((0,0),(1,0));d.modelspace().add_blockref('B',(0,0),dxfattribs={'row_count':2,'column_count':3,'row_spacing':2,'column_spacing':2})
 with pytest.raises(RuntimeError):read(d,p)

def test_hidden_insert_does_not_expose_visible_child_for_takeoff(tmp_path):
 d,p=drawing(tmp_path);d.layers.new('hidden');d.layers.get('hidden').off();d.layers.new('visible');b=d.blocks.new('B');b.add_line((0,0),(1,0),dxfattribs={'layer':'visible'});d.modelspace().add_blockref('B',(0,0),dxfattribs={'layer':'hidden'})
 child=next(e for e in read(d,p).entities if e.entity_type=='LINE');assert child.data['layer_visible'] is False

@pytest.mark.parametrize('rotation',[0,30,90])
def test_cad_text_baseline_and_cap_height_use_source_coordinates(tmp_path,rotation):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import QPointF
 from PySide6.QtGui import QFontMetricsF
 from app.graphical_takeoff import GraphicalTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([])
 d,p=drawing(tmp_path);d.modelspace().add_line((0,0),(3,4));t=d.modelspace().add_text('ستون C1 — ۱۲',dxfattribs={'insert':(1,1),'height':.5,'rotation':rotation});d.saveas(p)
 w=GraphicalTakeoffDialog(pdf_path=str(p));w.show();_qt.processEvents()
 try:
  item=w._cad_handle_items[t.dxf.handle];metrics=QFontMetricsF(item.font());baseline=item.mapToScene(QPointF(0,metrics.ascent()));ox,oy=w._cad_scene_origin
  assert baseline.x()==pytest.approx(1-ox,abs=1e-9) and baseline.y()==pytest.approx(oy-1,abs=1e-9)
  top=item.mapToScene(QPointF(0,metrics.ascent()-metrics.capHeight()));assert math.hypot(top.x()-baseline.x(),top.y()-baseline.y())==pytest.approx(.5,rel=1e-9)
  assert item.document().documentMargin()==0
 finally:w.close()

def test_cad_mtext_top_left_anchor_and_width_are_source_based(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import QPointF
 from app.graphical_takeoff import GraphicalTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([]);d,p=drawing(tmp_path);d.modelspace().add_line((0,0),(3,4));e=d.modelspace().add_mtext('طبقه\\Pاول',dxfattribs={'insert':(1,1),'char_height':.5,'width':3,'attachment_point':1});d.saveas(p)
 w=GraphicalTakeoffDialog(pdf_path=str(p));w.show();_qt.processEvents()
 try:
  item=w._cad_handle_items[e.dxf.handle];rect=item.sceneBoundingRect();ox,oy=w._cad_scene_origin
  assert rect.left()==pytest.approx(1-ox,abs=1e-9) and rect.top()==pytest.approx(oy-1,abs=1e-9)
  assert rect.width()==pytest.approx(3,rel=1e-9)
 finally:w.close()

def test_native_cad_hairline_mouse_pick_has_device_tolerance(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.graphical_takeoff import GraphicalTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([]);d,p=drawing(tmp_path);e=d.modelspace().add_line((0,0),(3,4));d.modelspace().add_circle((10,10),2);d.modelspace().add_text('ستون',dxfattribs={'insert':(1,1),'height':.5});d.saveas(p)
 w=GraphicalTakeoffDialog(pdf_path=str(p));w.resize(1400,1000);w.show();_qt.processEvents()
 try:
  QTest.mouseClick(w.cad_select,Qt.LeftButton);item=w._cad_handle_items[e.dxf.handle]
  for scale in (1.03,.91,1.17):
   w.canvas.scale_view(scale);w.canvas.scene.clearSelection();QTest.mouseClick(w.canvas.viewport(),Qt.LeftButton,pos=w.canvas.mapFromScene(item.line().pointAt(.9)));assert item.isSelected()
 finally:w.close()
