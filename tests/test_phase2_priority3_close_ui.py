"""Native Qt clicks/dialogs and real services, synthetic inputs only."""
from pathlib import Path
from time import monotonic
import json
import pytest
from PySide6.QtWidgets import QApplication,QInputDialog,QMessageBox,QDialogButtonBox,QFileDialog,QDialog,QLineEdit,QTabWidget,QScrollArea
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtTest import QTest
from app.graphical_takeoff import GraphicalTakeoffDialog
from app.roof_detail_editor import open_roof_editor
from test_phase2_pdf_roof import fixture
from test_phase2_planar_roof import bound_planar,KINDS
_qt=None


def show_control(control):
 window=control.window()
 for tabs in window.findChildren(QTabWidget):
  for index in range(tabs.count()):
   if tabs.widget(index).isAncestorOf(control):QTest.mouseClick(tabs.tabBar(),Qt.LeftButton,pos=tabs.tabBar().tabRect(index).center())
 parent=control.parentWidget()
 while parent:
  if isinstance(parent,QScrollArea):parent.ensureWidgetVisible(control)
  parent=parent.parentWidget()
 QApplication.processEvents()


def _select_roof_document(qt, owner, directory, filename, errors, timeout=4.0):
 timer=QTimer(qt);timer.setInterval(20);deadline=monotonic()+timeout
 state={'prepared':False,'clicked':False,'timed_out':False}
 def poll():
  f=qt.activeModalWidget()
  try:
   if state['timed_out'] and isinstance(f,QDialog) and f is not owner:
    timer.stop();QDialog.done(f,QDialog.Rejected);return
   if isinstance(f,QFileDialog) and f.parentWidget() is owner and f.windowTitle()=='جدول دیتایل صریح؛ صرفاً ورودی قابل بازبینی':
    edit=f.findChild(QLineEdit,'fileNameEdit');buttons=f.findChild(QDialogButtonBox)
    button=buttons.button(QDialogButtonBox.Open) if buttons else None
    if edit is not None and button is not None:
     if not state['prepared']:
      f.setDirectory(str(directory));edit.setFocus();QTest.keyClick(edit,Qt.Key_A,Qt.ControlModifier);QTest.keyClicks(edit,filename);state['prepared']=True
     if button.isVisible() and button.isEnabled() and not state['clicked']:
      state['clicked']=True;QTest.mouseClick(button,Qt.LeftButton)
   if monotonic()>=deadline and not state['timed_out']:
    state['timed_out']=True;errors.append('Timed out waiting for documented roof file dialog to close')
    if isinstance(f,QDialog) and f is not owner:timer.stop();QDialog.done(f,QDialog.Rejected)
  except Exception as exc:
   errors.append(repr(exc));timer.stop()
   if isinstance(f,QFileDialog):f.reject()
 timer.timeout.connect(poll);timer.start()
 return timer,state


def _click_roof_control(qt, owner, button, errors, timeout=4.0, *, prepared=False):
 if not prepared:show_control(button)
 timer=QTimer(qt);timer.setInterval(20);deadline=monotonic()+timeout
 state={'handled':False}
 def poll():
  modal=qt.activeModalWidget()
  if isinstance(modal,QMessageBox) and modal.parentWidget() is owner:
   target=modal.button(QMessageBox.Ok)
   if not state['handled'] and modal.windowTitle()=='کنترل دیتایل سقف' and target and target.isVisible() and target.isEnabled():
    state['handled']=True;errors.append(modal.text());QTest.mouseClick(target,Qt.LeftButton)
  if monotonic()>=deadline:
   errors.append('Timed out waiting for roof action to finish');timer.stop()
   if isinstance(modal,QDialog) and modal is not owner:QDialog.done(modal,QDialog.Rejected)
 timer.timeout.connect(poll);timer.start()
 try:QTest.mouseClick(button,Qt.LeftButton)
 finally:timer.stop()


def test_native_boundary_cut_components_remove_and_undo(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);app,_,_,_=fixture(tmp_path)
 d=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P');d.resize(1500,1100);d.show();_qt.processEvents();errors=[]
 def answer():
  w=_qt.activeModalWidget()
  try:
   if isinstance(w,QInputDialog):
    if w.windowTitle()!='حذف بازشو':w.setTextValue('explicit synthetic boundary cut');QTimer.singleShot(20,answer)
    QTest.mouseClick(w.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
   else:QTest.mouseClick(w.button(QMessageBox.Yes),Qt.LeftButton)
  except Exception as exc:
   errors.append(repr(exc))
   if w:w.reject()
 def draw(mode,pts):
  d.mode.setCurrentText(mode);_qt.processEvents()
  for x,y in pts:QTest.mouseClick(d.canvas.viewport(),Qt.LeftButton,pos=d.canvas.mapFromScene(QPointF(x,y)))
  QTimer.singleShot(20,answer);QTest.mouseClick(d.finish,Qt.LeftButton)
 try:
  assert d.mode.findText('بازشوی مرزی و چندقسمتی')>=0
  d.session.calibrate(1,50,1);d.canvas.resetTransform()
  draw('چندضلعی دقیق',[(100,100),(600,100),(600,600),(100,600)])
  QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center())
  draw('بازشوی مرزی و چندقسمتی',[(300,100),(400,100),(400,600),(300,600)])
  assert not errors and d.session.items[0].quantity==80
  QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center())
  assert d.geometry_components.count()==3
  d.geometry_components.setFocus();QTest.keyClick(d.geometry_components,Qt.Key_Down);_qt.processEvents()
  assert d.canvas._measurement_overlay.path().boundingRect().width()==200
  QTimer.singleShot(20,answer);QTest.mouseClick(d.remove_opening,Qt.LeftButton)
  assert d.session.items[0].quantity==100
  QTest.mouseClick(d.undo,Qt.LeftButton);assert d.session.items[0].quantity==80
  QTest.mouseClick(d.redo,Qt.LeftButton);assert d.session.items[0].quantity==100
  d.grab().save(str(tmp_path/'topology-v2-real-qt.png'))
 finally:d.close();app.store.close()

@pytest.mark.parametrize('kind',KINDS)
def test_existing_roof_editor_real_planar_schedule_and_boq(tmp_path,kind):
 global _qt
 _qt=QApplication.instance() or QApplication([]);app,s,i,rec,data=bound_planar(tmp_path,kind);errors=[]
 def drive():
  w=next((x for x in _qt.topLevelWidgets() if x.objectName()=='RoofDetailEditor' and x.isVisible()),None)
  if w is None:QTimer.singleShot(20,drive);return
  try:
   c=w.roof_controls
   def click(button):
    _click_roof_control(_qt,w,button,errors)
   c['floor'].setText('L1');c['id'].setText('S1');click(c['new'])
   assert c['shape'].findData('documented_planar')>=0
   c['plan'].setText(data['source']['plan_ref']);c['detail'].setText(data['source']['detail_ref'])
   show_control(c['import_detail']);file_timer,file_state=_select_roof_document(_qt,w,tmp_path,'detail.json',errors)
   try:_click_roof_control(_qt,w,c['import_detail'],errors,prepared=True)
   finally:file_timer.stop()
   assert file_state['clicked'],errors
   assert c['shape'].currentData()=='documented_planar'
   click(c['save']);assert app.get_aec_system('P',kind,'L1','S1')
   click(c['preview']);assert 'نیازمند اطلاعات' not in c['message'].text(),c['message'].text()
   c['reviewer'].setText('independent synthetic user');c['note'].setText('explicit local analytic oracle')
   click(c['review']);click(c['commit'])
   assert app.get_aec_system('P',kind,'L1','S1')['status']=='committed',c['message'].text()
   w.grab().save(str(tmp_path/(kind+'-planar-real-qt.png')))
  except Exception as exc:errors.append(repr(exc))
  finally:w.accept()
 QTimer.singleShot(30,drive)
 open_roof_editor(app,project_id='P',floor_id='L1',kind=kind,drawing_source=data['source'])
 assert not errors,errors
 assert app.open_project('P')['boq'];app.store.close()


def test_native_drawing_correction_review_apply_and_reload(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([])
 from test_phase2_polygon_amendments import setup
 from core.drawings.takeoff_session import DrawingTakeoffSession
 app,s,i,r,key=setup(tmp_path);record=app.load_drawing_takeoff_session('P',r['session_id'])
 proposed=DrawingTakeoffSession.from_dict(record['session']);points=[[100,100],[550,100],[550,600],[100,600]];proposed.edit_polygon(i.id,points)
 doc=app.drawing_amendment_document('P',key,proposed.to_dict(),expected_revision=1,expected_session_revision=2)
 path=tmp_path/'correction.json';path.write_text(json.dumps(doc,ensure_ascii=False))
 d=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P');d.resize(1500,1100);d.show();_qt.processEvents();errors=[]
 def input_value(value):
  w=_qt.activeModalWidget()
  try:
   assert isinstance(w,QInputDialog);w.setTextValue(value);QTest.mouseClick(w.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
  except Exception as exc:
   errors.append(repr(exc))
   if w:w.reject()
 try:
  assert hasattr(d,'drawing_amendment_button'),'missing real correction UI'
  QTimer.singleShot(20,lambda:input_value(r['session_id']));QTest.mouseClick(d.load_session_button,Qt.LeftButton)
  QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center())
  QTimer.singleShot(20,lambda:input_value(json.dumps(points)));QTest.mouseClick(d.edit_vertices,Qt.LeftButton)
  assert d.session.items[0].quantity==90
  def drive():
   w=_qt.activeModalWidget()
   try:
    assert w.objectName()=='DrawingPolygonCorrection';c=w.correction_controls
    for k,v in {'author':'synthetic UI author','reason':'explicit synthetic correction','reviewer':'independent synthetic UI reviewer','note':'90 square metre analytic oracle','path':str(path),'reference':'synthetic correction detail'}.items():c[k].setText(v)
    QTest.mouseClick(c['preview'],Qt.LeftButton);assert '90' in c['summary'].text()
    def yes():
     box=_qt.activeModalWidget();QTest.mouseClick(box.button(QMessageBox.Yes),Qt.LeftButton)
    QTimer.singleShot(20,yes);QTest.mouseClick(c['create'],Qt.LeftButton);assert c['id'].text()
    QTest.mouseClick(c['review'],Qt.LeftButton);QTest.mouseClick(c['apply'],Qt.LeftButton)
    assert app.open_project('P')['boq'][0]['quantity']==90
    QTest.mouseClick(c['load'],Qt.LeftButton);QTest.mouseClick(c['highlight'],Qt.LeftButton)
    assert d.canvas._measurement_overlay.path().boundingRect().width()==450
    w.grab().save(str(tmp_path/'drawing-correction-real-qt.png'))
   except Exception as exc:errors.append(repr(exc))
   finally:
    if w:w.accept()
  QTimer.singleShot(20,drive);QTest.mouseClick(d.drawing_amendment_button,Qt.LeftButton)
  assert not errors,errors
 finally:d.close();app.store.close()


def test_pdf_roof_button_collects_real_local_frame(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([]);app,s,i,r,data=bound_planar(tmp_path,'solid_slab');errors=[];seen=[]
 d=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P');d.resize(1500,1100);d.show();_qt.processEvents()
 def restore():
  w=_qt.activeModalWidget();w.setTextValue(r['session_id']);QTest.mouseClick(w.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
 QTimer.singleShot(20,restore);QTest.mouseClick(d.load_session_button,Qt.LeftButton)
 QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center())
 def drive():
  w=_qt.activeModalWidget()
  try:
   if isinstance(w,QInputDialog):
    seen.append('kind');QTimer.singleShot(20,drive);QTest.mouseClick(w.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
   elif w.objectName()=='RoofLocalFrame':
    seen.append('frame');c=w.frame_controls
    values={'origin_x':'200','origin_y':'100','axis_x':'.8','axis_y':'.6','reference':'explicit synthetic 3-4-5 survey frame','reviewer':'synthetic frame reviewer'}
    for key,value in values.items():QTest.keyClicks(c[key],value)
    QTimer.singleShot(20,drive);QTest.mouseClick(c['confirm'],Qt.LeftButton)
   elif w.objectName()=='RoofDetailEditor':
    seen.append('editor');c=w.roof_controls;c['id'].setText('S1');QTest.mouseClick(c['new'],Qt.LeftButton)
    captured=c['capture']();assert captured['roof_detail']['geometry']['shape']=='documented_planar'
    assert captured['source']['roof_binding']['local_frame']['axis_x']==['.8','.6']
    w.accept()
   else:
    errors.append(w.text() if isinstance(w,QMessageBox) else repr(w))
    if isinstance(w,QMessageBox):QTest.mouseClick(w.button(QMessageBox.Ok),Qt.LeftButton)
    else:w.reject()
  except Exception as exc:
   errors.append(repr(exc))
   if w:w.reject()
 try:
  QTimer.singleShot(20,drive);QTest.mouseClick(d.region_to_roof,Qt.LeftButton)
  assert not errors and seen==['kind','frame','editor'],(errors,seen)
 finally:d.close();app.store.close()


def test_real_roof_geometry_revision_through_existing_amendment_buttons(tmp_path):
 global _qt
 _qt=QApplication.instance() or QApplication([])
 from test_phase2_planar_roof import prepared_geometry_revision
 app,_,_,_,_,original,proposal,_,_,_=prepared_geometry_revision(tmp_path);errors=[]
 def drive():
  w=next((w for w in _qt.topLevelWidgets() if w.objectName()=='RoofDetailEditor' and w.isVisible()),None)
  if w is None:QTimer.singleShot(20,drive);return
  try:
   c=w.roof_controls;c['id'].setText('S1')
   def click(button):
    _click_roof_control(_qt,w,button,errors)
   click(c['load']);assert 'source_geometry_amendment' in c,'missing explicit measured-source revision control'
   show_control(c['source_geometry_amendment']);QTest.mouseClick(c['source_geometry_amendment'],Qt.LeftButton,pos=c['source_geometry_amendment'].rect().topRight()+QPointF(-10,10).toPoint())
   assert c['source_geometry_amendment'].isChecked()
   show_control(c['import_detail']);file_timer,file_state=_select_roof_document(_qt,w,tmp_path,'roof-geometry-amendment.json',errors)
   try:_click_roof_control(_qt,w,c['import_detail'],errors,prepared=True)
   finally:file_timer.stop()
   assert file_state['clicked'],errors
   c['creator'].setText('synthetic UI author');c['reason'].setText('one explicit vertex and bound source revision')
   c['evidence_path'].setText(str(tmp_path/'roof-geometry-amendment.json'));c['evidence_ref'].setText('explicit synthetic revised detail')
   c['reviewer'].setText('independent synthetic UI reviewer');c['note'].setText('13 m2 / 2.6 m3 analytic oracle')
   click(c['create_amendment']);assert c['amend_id'].text(),c['message'].text()
   click(c['review_amendment']);click(c['apply_amendment'])
   assert app.get_aec_system('P','solid_slab','L1','S1')['revision']==3,c['message'].text()
   assert app.open_project('P')['takeoffs']==original['takeoffs']
   w.grab().save(str(tmp_path/'roof-geometry-correction-real-qt.png'))
  except Exception as exc:errors.append(repr(exc))
  finally:w.accept()
 QTimer.singleShot(20,drive);open_roof_editor(app,project_id='P',floor_id='L1',kind='solid_slab',drawing_source=proposal['source'])
 assert not errors,errors;app.store.close()


def test_delayed_file_dialog_does_not_reject_its_roof_parent(tmp_path):
 global _qt
 from PySide6.QtCore import QEventLoop
 _qt=QApplication.instance() or QApplication([]);errors=[];selected=[]
 document=tmp_path/'detail.json';document.write_text('{}')
 parent=QDialog();parent.setObjectName('RoofDetailEditor');parent.setModal(True);parent.show();_qt.processEvents()
 loop=QEventLoop()
 timer,state=_select_roof_document(_qt,parent,tmp_path,'detail.json',errors)
 def delayed_file():
  f=QFileDialog(parent,'جدول دیتایل صریح؛ صرفاً ورودی قابل بازبینی',str(tmp_path),'JSON (*.json)')
  f.setOption(QFileDialog.DontUseNativeDialog);f.setFileMode(QFileDialog.ExistingFile)
  f.exec();selected.extend(f.selectedFiles())
 QTimer.singleShot(80,delayed_file);QTimer.singleShot(900,loop.quit)
 loop.exec();timer.stop();was_visible=parent.isVisible();parent.close();_qt.processEvents()
 assert not errors and was_visible and state['clicked'],errors
 assert len(selected)==1 and Path(selected[0])==document
