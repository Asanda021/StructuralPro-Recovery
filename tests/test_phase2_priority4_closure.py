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
  start=time.monotonic();ticks.append(start);w.open_cad_async(str(p));wait(lambda:not w.cad_loading);elapsed=time.monotonic()-start;QTest.qWait(30)
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

@pytest.mark.parametrize('kind,metric,expected',[('CIRCLE','length',4*math.pi),('CIRCLE','area',4*math.pi),('ARC','length',math.pi),('INSERT','length',10),('MINSERT','length',30)])
def test_analytic_and_block_boq(tmp_path,kind,metric,expected):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from copy import deepcopy
 d=ezdxf.new('R2018');d.units=6;m=d.modelspace()
 if kind=='CIRCLE':e=m.add_circle((0,0),2)
 elif kind=='ARC':e=m.add_arc((0,0),2,0,90)
 else:
  b=d.blocks.new('B');b.add_line((0,0),(3,4))
  if kind=='INSERT':b.add_line((10,0),(13,4))
  e=m.add_blockref('B',(10,20),dxfattribs={'row_count':2,'column_count':3,'row_spacing':7,'column_spacing':9,'rotation':90} if kind=='MINSERT' else {})
 p=tmp_path/'source.dxf';d.saveas(p);doc=DWGTakeoffEngine.with_array_support().import_file(p)
 app=StructuralProApp(tmp_path/'db');app.create_project('synthetic','P');app.add_project_floor('P','floor',level='L1');app.add_project_member('P','M1','L1','member');app.add_project_member('P','M2','L1','other member')
 s=DrawingTakeoffSession(str(p))
 try:
  i=s.add_cad_entity(doc,e.dxf.handle,metric,takeoff_code='operation',floor_id='L1',member_id='M1',quantity_owner='explicit synthetic sole owner',created_by='author',reference='explicit analytic oracle')
  assert i.quantity==pytest.approx(expected,rel=1e-12)
  s.review_cad_entity(i.id,reviewer='other',note='independent analytic check');r=app.save_drawing_takeoff_session('P',s);app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
  assert app.open_project('P')['boq'][0]['quantity']==pytest.approx(expected,rel=1e-12)
  if kind=='INSERT':
   t=DrawingTakeoffSession(str(p));child=next(x for x in doc.entities if x.entity_type=='LINE');j=t.add_cad_entity(doc,child.handle,'length',takeoff_code='renamed',floor_id='L1',member_id='M2',quantity_owner='other claim',created_by='author',reference='same child');t.review_cad_entity(j.id,reviewer='other',note='reviewed');rr=app.save_drawing_takeoff_session('P',t);before=deepcopy(app.open_project('P'))
   with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rr['session_id'],[j.id],expected_session_revision=1)
   assert app.open_project('P')==before
 finally:app.store.close()

def test_native_block_find_and_unit_form(tmp_path):
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtWidgets import QDialog,QLineEdit,QPushButton,QMessageBox
 app=qt();d=ezdxf.new('R2018');d.units=0;b=d.blocks.new('B');b.add_line((0,0),(3,4));b.add_line((10,0),(13,4));root=d.modelspace().add_blockref('B',(0,0));p=tmp_path/'unitless.dxf';d.saveas(p)
 w=GraphicalTakeoffDialog(pdf_path=str(p));w.show();app.processEvents()
 try:
  w.cad_handle.setText(root.dxf.handle);QTest.mouseClick(w.cad_find,Qt.LeftButton);assert len(w.canvas.scene.selectedItems())==2
  proof={'policy':'cad_unit_reference_v1','source_sha256':w.cad_document.source_sha256,'unit':'mm','reference_handle':next(e.handle for e in w.cad_document.entities if e.entity_type=='LINE'),'cad_length':'5','real_length_m':'0.005','author':'author','reviewer':'other','reference':'Explicit synthetic known length'}
  f=tmp_path/'unit.json';f.write_text(json.dumps(proof));errors=[]
  def confirm():
   modal=app.activeModalWidget()
   if isinstance(modal,QMessageBox):QTest.mouseClick(modal.button(QMessageBox.Yes),Qt.LeftButton)
  def fill():
   modal=app.activeModalWidget()
   try:
    assert isinstance(modal,QDialog);modal.findChild(QLineEdit,'cad_unit_document').setText(str(f));QTimer.singleShot(20,confirm);QTest.mouseClick(modal.findChild(QPushButton,'cad_unit_apply'),Qt.LeftButton)
   except Exception as exc:errors.append(str(exc));modal.reject()
  QTimer.singleShot(20,fill);QTest.mouseClick(w.cad_unit_button,Qt.LeftButton)
  assert not errors and w.cad_document.units=='mm';assert sum(e.data.get('length',0) for e in w.cad_document.entities)==pytest.approx(.01)
  w.grab().save(str(tmp_path/'documented-unit-qt.png'))
 finally:w.close()

@pytest.mark.parametrize('fault',['self_review','negative','zero','wrong_calibration','conflict','source','missing'])
def test_unit_evidence_fail_closed(tmp_path,fault):
 from core.drawings.dwg_takeoff import apply_documented_units
 p=fixture(tmp_path,unit=6 if fault=='conflict' else 0);doc=DWGTakeoffEngine().import_file(p)
 proof={'policy':'cad_unit_reference_v1','source_sha256':doc.source_sha256,'unit':'mm','reference_handle':doc.entities[0].handle,'cad_length':'5','real_length_m':'0.005','author':'author','reviewer':'other','reference':'Explicit synthetic reference'}
 if fault=='self_review':proof['reviewer']='author'
 if fault=='negative':proof['real_length_m']='-0.005'
 if fault=='zero':proof['cad_length']='0'
 if fault=='wrong_calibration':proof['real_length_m']='0.006'
 if fault=='source':proof['source_sha256']='0'*64
 f=tmp_path/'proof.json';f.write_text(json.dumps(proof));e={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 if fault=='missing':f.unlink()
 with pytest.raises(ValueError):apply_documented_units(doc,e)

def test_unitless_sqlite_review_cas_and_document_change(tmp_path):
 from core.drawings.dwg_takeoff import apply_documented_units
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from core.platform.application import StructuralProApp
 from copy import deepcopy
 p=fixture(tmp_path,unit=0);raw=DWGTakeoffEngine().import_file(p)
 proof={'policy':'cad_unit_reference_v1','source_sha256':raw.source_sha256,'unit':'mm','reference_handle':raw.entities[0].handle,'cad_length':'5','real_length_m':'0.005','author':'author','reviewer':'other','reference':'Explicit synthetic dimension'}
 f=tmp_path/'unit-proof.json';f.write_text(json.dumps(proof));e={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()};doc=apply_documented_units(raw,e)
 app=StructuralProApp(tmp_path/'db');app.create_project('synthetic','P');app.add_project_floor('P','floor',level='L1');app.add_project_member('P','M1','L1','member');s=DrawingTakeoffSession(str(p));i=s.add_cad_entity(doc,raw.entities[0].handle,'length',takeoff_code='quantity',floor_id='L1',member_id='M1',quantity_owner='explicit owner',created_by='author',reference='synthetic')
 try:
  s.review_cad_entity(i.id,reviewer='other',note='unit and dimension checked');r=app.save_drawing_takeoff_session('P',s);before=deepcopy(app.open_project('P'))
  f.write_text('{}')
  with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
  assert app.open_project('P')==before
  f.write_text(json.dumps(proof));app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
  app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')['boq'][0]['quantity']==.005
  restored=app.load_drawing_takeoff_session('P',r['session_id']);assert restored['session']['items'][0]['cad_evidence']['unit_evidence']==e
  before=deepcopy(app.open_project('P'))
  with pytest.raises(RuntimeError,match='تعارض نسخه'):app.save_drawing_takeoff_session('P',s,session_id=r['session_id'],expected_revision=0)
  assert app.open_project('P')==before
 finally:app.store.close()

@pytest.mark.parametrize('fault',['spacing','cycle','too_many','xref','block_units','z'])
def test_array_and_block_fail_closed(tmp_path,fault):
 from core.drawings.dwg_takeoff import cad_entity_geometry
 d=ezdxf.new('R2018');d.units=6;b=d.blocks.new('B');b.add_line((0,0),(3,4,1 if fault=='z' else 0))
 if fault=='block_units':b.block_record.dxf.units=4
 if fault=='cycle':b.add_blockref('B',(0,0))
 if fault=='xref':b.block.dxf.flags=4;b.block.dxf.xref_path='missing.dwg'
 attr={'row_count':2,'column_count':2,'row_spacing':-1 if fault=='spacing' else 5,'column_spacing':5}
 if fault=='too_many':attr.update(row_count=501,column_count=501)
 root=d.modelspace().add_blockref('B',(0,0),dxfattribs=attr);p=tmp_path/'array.dxf';d.saveas(p)
 if fault in {'spacing','cycle','too_many'}:
  with pytest.raises(RuntimeError):DWGTakeoffEngine.with_array_support().import_file(p)
 else:
  doc=DWGTakeoffEngine.with_array_support().import_file(p)
  with pytest.raises(ValueError):cad_entity_geometry(doc,root.dxf.handle,'length')

def test_same_batch_parent_child_are_not_second_payment(tmp_path):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from copy import deepcopy
 d=ezdxf.new('R2018');d.units=6;b=d.blocks.new('B');b.add_line((0,0),(3,4));b.add_line((10,0),(13,4));root=d.modelspace().add_blockref('B',(0,0));p=tmp_path/'source.dxf';d.saveas(p);doc=DWGTakeoffEngine.with_array_support().import_file(p)
 app=StructuralProApp(tmp_path/'db');app.create_project('synthetic','P');app.add_project_floor('P','floor',level='L1')
 for member in ('M1','M2'):app.add_project_member('P',member,'L1','member')
 s=DrawingTakeoffSession(str(p))
 try:
  for h,member in [(root.dxf.handle,'M1'),(next(e.handle for e in doc.entities if e.entity_type=='LINE'),'M2')]:
   i=s.add_cad_entity(doc,h,'length',takeoff_code=member,floor_id='L1',member_id=member,quantity_owner='explicit owner',created_by='author',reference='same physical child');s.review_cad_entity(i.id,reviewer='other',note='oracle')
  r=app.save_drawing_takeoff_session('P',s);before=deepcopy(app.open_project('P'))
  with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id for i in s.items],expected_session_revision=1)
  assert app.open_project('P')==before
 finally:app.store.close()

def test_cancel_during_render_and_close_active_worker_preserve_db(tmp_path):
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from core.platform.application import StructuralProApp
 from PySide6.QtTest import QTest
 from PySide6.QtCore import QTimer
 from copy import deepcopy
 qt();p=fixture(tmp_path);large=fixture(tmp_path,10000);app=StructuralProApp(tmp_path/'db');app.create_project('synthetic','P');before=deepcopy(app.open_project('P'));w=GraphicalTakeoffDialog(pdf_path=str(p),app_service=app,project_id='P');w.show()
 try:
  w.open_cad_async(str(large));wait(lambda:not w.cad_loading or bool(w._cad_job.get('old')))
  assert w.cad_loading;w.cancel_cad_loading();assert w.viewer.path==p and len(w.cad_document.entities)==1
  w.open_cad_async(str(large));QTest.qWait(20);w.close();assert not w.cad_loading and w._cad_job is None;assert app.open_project('P')==before
 finally:w.close();app.store.close()

def test_changed_handle_same_geometry_requires_reconciliation(tmp_path):
 from core.platform.application import StructuralProApp
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from copy import deepcopy
 p=fixture(tmp_path);app=StructuralProApp(tmp_path/'db');app.create_project('synthetic','P');app.add_project_floor('P','floor',level='L1')
 for member in ('M1','M2'):app.add_project_member('P',member,'L1','member')
 original=p.read_bytes()
 try:
  for member in ('M1','M2'):
   doc=DWGTakeoffEngine().import_file(p);s=DrawingTakeoffSession(str(p));i=s.add_cad_entity(doc,doc.entities[0].handle,'length',takeoff_code=member,floor_id='L1',member_id=member,quantity_owner='explicit owner',created_by='author',reference='same geometric part');s.review_cad_entity(i.id,reviewer='other',note='5 m');r=app.save_drawing_takeoff_session('P',s)
   if member=='M1':
    app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1);d=ezdxf.readfile(p);d.modelspace()[0].dxf.handle='ABC';d.saveas(p)
   else:
    before=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
    assert app.open_project('P')==before
 finally:p.write_bytes(original);app.store.close()

@pytest.mark.parametrize('kind',['HATCH','DIMENSION','SPLINE','ELLIPSE','BULGE'])
def test_nonfinancial_entities_are_explicitly_blocked(tmp_path,kind):
 from core.drawings.dwg_takeoff import cad_entity_geometry
 d=ezdxf.new('R2018');d.units=6;m=d.modelspace()
 if kind=='HATCH':e=m.add_hatch();e.paths.add_polyline_path([(0,0),(2,0),(2,2),(0,2)],is_closed=True)
 elif kind=='DIMENSION':e=m.add_linear_dim(base=(0,2),p1=(0,0),p2=(3,0)).dimension
 elif kind=='SPLINE':e=m.add_spline([(0,0),(1,2),(3,0)])
 elif kind=='ELLIPSE':e=m.add_ellipse((0,0),major_axis=(3,0),ratio=.5)
 else:e=m.add_lwpolyline([(0,0,1),(2,0,0)],format='xyb')
 p=tmp_path/'nonfinancial.dxf';d.saveas(p);doc=DWGTakeoffEngine().import_file(p)
 with pytest.raises(ValueError):cad_entity_geometry(doc,e.dxf.handle,'length')
 assert kind=='BULGE' or any(x.data.get('unsupported_measurement') for x in doc.entities)

def test_rotated_block_persian_text_is_display_only(tmp_path):
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt
 app=qt();d=ezdxf.new('R2018');d.units=6;b=d.blocks.new('B');b.add_line((0,0),(3,4));b.add_mtext('ستون C1 — ۱۲\\Pطبقه اول',dxfattribs={'insert':(2,3),'char_height':.5,'width':4});root=d.modelspace().add_blockref('B',(10,20),dxfattribs={'rotation':90});p=tmp_path/'persian.dxf';d.saveas(p)
 w=GraphicalTakeoffDialog(pdf_path=str(p));w.show();app.processEvents()
 try:
  text=next(e for e in w.cad_document.entities if e.entity_type=='MTEXT');assert text.data['insert']==pytest.approx((7,22));assert text.data['font_notice']
  before=text.data.copy();item=w._cad_handle_items[text.handle];assert 'ستون' in item.toPlainText()
  for _ in range(3):QTest.mouseClick(w.zoom_in,Qt.LeftButton);QTest.mouseClick(w.zoom_out,Qt.LeftButton)
  w.cad_handle.setText(root.dxf.handle);QTest.mouseClick(w.cad_find,Qt.LeftButton);assert len(w.canvas.scene.selectedItems())==2 and text.data==before
  w.grab().save(str(tmp_path/'persian-block-qt.png'))
 finally:w.close()

def test_documented_unit_empty_draft_roundtrip_and_undo(tmp_path):
 from core.drawings.takeoff_session import DrawingTakeoffSession
 p=fixture(tmp_path,unit=0);doc=DWGTakeoffEngine().import_file(p);s=DrawingTakeoffSession(str(p))
 proof={'policy':'cad_unit_reference_v1','source_sha256':doc.source_sha256,'unit':'mm','reference_handle':doc.entities[0].handle,'cad_length':'5','real_length_m':'0.005','author':'author','reviewer':'other','reference':'Explicit synthetic reference'}
 f=tmp_path/'proof.json';f.write_text(json.dumps(proof));e={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
 assert hasattr(s,'set_cad_units');s.set_cad_units(doc,e)
 t=DrawingTakeoffSession.from_dict(s.to_dict());assert t.cad_unit_evidence==e
 s.undo();assert s.cad_unit_evidence is None;s.redo();assert s.cad_unit_evidence==e

def test_cad_analytic_revision_uses_existing_journal(tmp_path):
 from core.drawings.takeoff_session import DrawingTakeoffSession
 from core.platform.application import StructuralProApp
 from copy import deepcopy
 app=StructuralProApp(tmp_path/'db');app.create_project('synthetic','P');app.add_project_floor('P','floor',level='L1');app.add_project_member('P','M1','L1','member')
 def measured(name,radius):
  d=ezdxf.new('R2018');d.units=6;e=d.modelspace().add_circle((0,0),radius);p=tmp_path/name;d.saveas(p);doc=DWGTakeoffEngine().import_file(p);s=DrawingTakeoffSession(str(p));i=s.add_cad_entity(doc,e.dxf.handle,'length',takeoff_code='circumference',floor_id='L1',member_id='M1',quantity_owner='sole owner',created_by='author',reference='explicit radius');s.review_cad_entity(i.id,reviewer='other',note='2 pi r');return s,i
 try:
  s,i=measured('old.dxf',2);r=app.save_drawing_takeoff_session('P',s);app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1);original=deepcopy(app.open_project('P'));key=original['takeoffs'][0]['source_id'];new,j=measured('new.dxf',3)
  doc=app.drawing_amendment_document('P',key,new.to_dict(),expected_revision=1,expected_session_revision=2);p=tmp_path/'revision.json';p.write_text(json.dumps(doc));a=app.create_drawing_amendment('P',key,new.to_dict(),expected_revision=1,expected_session_revision=2,created_by='author',reason='explicit radius revision',evidence={'evidence_path':str(p),'evidence_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'evidence_reference':'synthetic'})
  app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='6 pi');app.apply_beam_amendment('P',a['id'],expected_revision=1);final=app.open_project('P');assert final['takeoffs']==original['takeoffs'];assert final['boq'][0]['quantity']==pytest.approx(6*math.pi)
  with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
 finally:app.store.close()

def test_native_capability_report_has_persian_blocking_reason(tmp_path):
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from PySide6.QtWidgets import QDialog,QTableWidget
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 app=qt();d=ezdxf.new('R2018');d.units=6;h=d.modelspace().add_hatch();h.paths.add_polyline_path([(0,0),(1,0),(1,1)],is_closed=True);p=tmp_path/'hatch.dxf';d.saveas(p);w=GraphicalTakeoffDialog(pdf_path=str(p));w.show();errors=[]
 try:
  assert hasattr(w,'cad_report')
  def inspect():
   modal=app.activeModalWidget()
   try:
    table=modal.findChild(QTableWidget);assert table.rowCount()==1;assert 'HATCH' in table.item(0,0).text() and 'پشتیبانی' in table.item(0,2).text()
   except Exception as exc:errors.append(str(exc))
   finally:modal.accept()
  QTimer.singleShot(20,inspect);QTest.mouseClick(w.cad_report,Qt.LeftButton);assert not errors
 finally:w.close()
