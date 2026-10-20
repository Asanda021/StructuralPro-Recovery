"""Actual desktop controls, drawing identity and nonfinancial steel SQLite UI."""
import os,sys,json,subprocess
from pathlib import Path
from copy import deepcopy
import pytest


def test_real_shell_theme_motion_and_persistence(tmp_path):
 script=Path(__file__).with_name('phase1_final_desktop_probe.py')
 p=subprocess.run([sys.executable,str(script),str(tmp_path),'closure'],cwd=script.parents[1],env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},capture_output=True,text=True,timeout=60)
 assert p.returncode==0,p.stdout+p.stderr


def test_float_slide_and_row_highlight_never_change_measurements(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt,QEvent,QCoreApplication
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from core.platform.application import StructuralProApp
 from core.drawings.graphical_takeoff import Point
 from drawing_source_fixture import vector_pdf
 global _qt
 _qt=QApplication.instance() or QApplication([]);_qt.setProperty('structuralproAnimationsEnabled',True)
 s=StructuralProApp(tmp_path/'db');s.create_project('مصنوعی؛ کنترل تعامل','P')
 d=GraphicalTakeoffDialog(pdf_path=vector_pdf(tmp_path),app_service=s,project_id='P');d.show();_qt.processEvents()
 try:
  assert d.layoutDirection()==Qt.RightToLeft
  d.session.calibrate(1,100,10);item=d.session.add_area([Point(100,100),Point(200,100),Point(200,150),Point(100,150)],page=1,label='عضو مصنوعی صریح')
  before=deepcopy(d.session.to_dict());project=deepcopy(s.open_project('P'));d.refresh()
  assert d.beam_dock.isHidden()
  QTest.mouseClick(d.panel_toggle,Qt.LeftButton);assert d.beam_dock.isVisible()
  QTest.mouseClick(d.panel_float,Qt.LeftButton);assert d.beam_dock.isFloating()
  QTest.mouseClick(d.panel_float,Qt.LeftButton);assert not d.beam_dock.isFloating()
  d.table.scrollToItem(d.table.item(0,0));QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center());_qt.processEvents()
  assert d.canvas._highlighted_item_id==item.id and d.canvas._measurement_overlay is not None
  assert d.beam_dock.isVisible()
  QTest.qWait(400);assert d.canvas._measurement_overlay is not None
  _qt.setProperty('structuralproAnimationsEnabled',False)
  d.highlight_selected_measurement();assert d.canvas._highlight_animation is None or d.canvas._highlight_animation.state()==d.canvas._highlight_animation.Stopped
  assert d.session.to_dict()==before and s.open_project('P')==project
  assert d.grab().save(str(tmp_path/'drawing-after.png'))
  QTest.mouseClick(d.panel_toggle,Qt.LeftButton);assert not d.beam_dock.isVisible()
 finally:
  d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);_qt.processEvents();s.store.close()


def test_steel_stair_real_form_save_check_reopen_and_stale_cas(tmp_path,monkeypatch):
 from PySide6.QtWidgets import QApplication,QFileDialog
 from PySide6.QtCore import Qt,QTimer,QEvent,QCoreApplication
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from core.takeoff.structural_handoff_work import STEEL_SUPPORT_POLICY
 from app.structural_handoff_audit_editor import open_structural_handoff_audit
 from test_phase1_package2_service import steel_case
 global _qt
 _qt=QApplication.instance() or QApplication([])
 s,request,args=steel_case(tmp_path);before=deepcopy(s.open_project('P'));errors=[];seen=[]
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(args['source_path'],''))
 def first():
  dlg=_qt.activeModalWidget()
  try:
   c=dlg.handoff_controls;c['audit_id'].setText('STEEL-UI');c['evidence_files'].setPlainText(json.dumps(args['evidence_files']))
   QTest.mouseClick(c['load'],Qt.LeftButton);QTest.mouseClick(c['save_draft'],Qt.LeftButton)
   assert c['revision']==1,c['message'].text()
   QTest.mouseClick(c['run_saved'],Qt.LeftButton)
   assert c['revision']==2,c['message'].text()
   result=s.get_structural_handoff_audit('P','STEEL-UI')['result'];assert result['document_consistent']
   assert not result['ready'] and not result['commit_allowed'] and result['payable_rows']==[]
   assert s.open_project('P')['boq']==before['boq']
   assert dlg.grab().save(str(tmp_path/'steel-after.png'));seen.append('saved')
  except Exception as e:errors.append(repr(e))
  finally:dlg.reject()
 QTimer.singleShot(30,first)
 dlg=open_structural_handoff_audit(s,project_id='P',required_policy=STEEL_SUPPORT_POLICY)
 dlg.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);s.store.close();s=StructuralProApp(tmp_path/'db')
 def reopened():
  dlg=_qt.activeModalWidget()
  try:
   c=dlg.handoff_controls;c['audit_id'].setText('STEEL-UI');QTest.mouseClick(c['reopen'],Qt.LeftButton)
   assert c['revision']==2 and c['result']['commit_allowed'] is False
   peer=StructuralProApp(tmp_path/'db');peer.run_structural_handoff_audit('P','STEEL-UI',expected_revision=2);peer.store.close()
   state=deepcopy(s.open_project('P'));QTest.mouseClick(c['run_saved'],Qt.LeftButton)
   assert 'خطا' in c['message'].text() and s.open_project('P')==state
   seen.append('reopened-cas')
  except Exception as e:errors.append(repr(e))
  finally:dlg.reject()
 QTimer.singleShot(30,reopened);dlg=open_structural_handoff_audit(s,project_id='P',required_policy=STEEL_SUPPORT_POLICY)
 dlg.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);s.store.close()
 assert not errors,errors
 assert seen==['saved','reopened-cas']


@pytest.mark.parametrize('bad',['non_object','wrong_policy','changed_bytes'])
def test_steel_form_rejects_untrusted_input_without_sql_write(tmp_path,monkeypatch,bad):
 from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.structural_handoff_audit_editor import open_structural_handoff_audit
 from core.takeoff.structural_handoff_work import STEEL_SUPPORT_POLICY
 from test_phase1_package2_service import steel_case
 global _qt
 _qt=QApplication.instance() or QApplication([]);s,request,args=steel_case(tmp_path)
 source=Path(args['source_path'])
 if bad=='non_object':source.write_text('[]')
 if bad=='wrong_policy':source.write_text(json.dumps({**request,'policy':'six_family_geometry_service_work_v1'}))
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(source),''))
 monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.Yes)
 before='\n'.join(s.store.db.iterdump());errors=[]
 def run():
  d=_qt.activeModalWidget()
  try:
   c=d.handoff_controls;c['audit_id'].setText('BAD');c['evidence_files'].setPlainText(json.dumps(args['evidence_files']))
   QTest.mouseClick(c['load'],Qt.LeftButton)
   if bad=='changed_bytes':
    Path(next(iter(args['evidence_files'].values()))).write_bytes(b'altered')
    QTest.mouseClick(c['save_draft'],Qt.LeftButton)
   assert 'خطا' in c['message'].text(),c['message'].text()
   assert c['revision']==0 and '\n'.join(s.store.db.iterdump())==before
  except Exception as e:errors.append(repr(e))
  finally:d.reject()
 QTimer.singleShot(30,run);open_structural_handoff_audit(s,project_id='P',required_policy=STEEL_SUPPORT_POLICY);s.store.close();assert not errors,errors


def test_steel_form_is_opened_from_existing_aec_menu(tmp_path,monkeypatch):
 from PySide6.QtWidgets import QApplication,QMessageBox
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 from core.platform.application import StructuralProApp
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path/'db');s.create_project('مصنوعی','P');seen=[];errors=[]
 monkeypatch.setattr(QMessageBox,'warning',lambda *a:None)
 def parent():
  p=_qt.activeModalWidget()
  def child():
   d=_qt.activeModalWidget()
   try:assert hasattr(d,'handoff_controls');assert not d.handoff_controls['save_draft'].isEnabled();seen.append('steel-menu')
   except Exception as e:errors.append(repr(e))
   finally:d.reject()
  try:QTimer.singleShot(30,child);QTest.mouseClick(p.steel_stair_button,Qt.LeftButton)
  except Exception as e:errors.append(repr(e))
  finally:p.reject()
 QTimer.singleShot(30,parent);open_reviewed_aec_editor(s,project_id='P',floor_id='L1');s.store.close();assert seen==['steel-menu'] and not errors,errors


def test_drawing_table_does_not_round_nonzero_length_to_zero(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import QEvent,QCoreApplication
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from core.drawings.graphical_takeoff import Point
 from drawing_source_fixture import vector_pdf
 global _qt
 _qt=QApplication.instance() or QApplication([]);d=GraphicalTakeoffDialog(pdf_path=vector_pdf(tmp_path))
 try:
  d.session.calibrate(1,100,10);item=d.session.add_length([Point(0,0),Point(.0000000001,0)],page=1,label='طول صریح کوچک مصنوعی');d.refresh()
  assert d.table.item(0,4).text()==str(item.quantity) and item.quantity>0
  assert d.table.item(0,2).text()=='طول'
 finally:d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_unsaved_audit_bindings_need_real_discard_confirmation(tmp_path,monkeypatch):
 from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.structural_handoff_audit_editor import open_structural_handoff_audit
 from core.takeoff.structural_handoff_work import STEEL_SUPPORT_POLICY
 from test_phase1_package2_service import steel_case
 global _qt
 _qt=QApplication.instance() or QApplication([]);s,request,args=steel_case(tmp_path);before=deepcopy(s.open_project('P'));errors=[];seen=[]
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(args['source_path'],''))
 def exercise():
  d=_qt.activeModalWidget();answer=[QMessageBox.No];timer=QTimer(d)
  def choose():
   box=_qt.activeModalWidget()
   if isinstance(box,QMessageBox):QTest.mouseClick(box.button(answer[0]),Qt.LeftButton)
  timer.timeout.connect(choose);timer.start(10)
  try:
   c=d.handoff_controls;c['audit_id'].setText('UNSAVED');c['evidence_files'].setPlainText(json.dumps(args['evidence_files']));QTest.mouseClick(c['load'],Qt.LeftButton)
   QTest.mouseClick(c['close'],Qt.LeftButton);assert d.isVisible(),'Unsaved source bindings must not disappear without confirmation'
   seen.append('cancelled');answer[0]=QMessageBox.Yes;QTest.mouseClick(c['close'],Qt.LeftButton);assert not d.isVisible();seen.append('discarded')
  except Exception as e:errors.append(repr(e))
  finally:timer.stop();d.reject()
 QTimer.singleShot(30,exercise);open_structural_handoff_audit(s,project_id='P',required_policy=STEEL_SUPPORT_POLICY)
 assert s.open_project('P')==before;s.store.close();assert seen==['cancelled','discarded'] and not errors,errors
