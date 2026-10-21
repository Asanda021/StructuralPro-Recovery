"""Native Qt clicks/dialogs and real services, synthetic inputs only."""
from pathlib import Path
import json
import pytest
from PySide6.QtWidgets import QApplication,QInputDialog,QMessageBox,QDialogButtonBox,QFileDialog,QDialog,QLineEdit
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtTest import QTest
from app.graphical_takeoff import GraphicalTakeoffDialog
from app.roof_detail_editor import open_roof_editor
from test_phase2_pdf_roof import fixture
from test_phase2_planar_roof import bound_planar,KINDS
_qt=None


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
    def alert():
     modal=_qt.activeModalWidget()
     if isinstance(modal,QMessageBox):
      errors.append(modal.text());QTest.mouseClick(modal.button(QMessageBox.Ok),Qt.LeftButton)
    QTimer.singleShot(30,alert);QTest.mouseClick(button,Qt.LeftButton)
   c['floor'].setText('L1');c['id'].setText('S1');click(c['new'])
   assert c['shape'].findData('documented_planar')>=0
   c['plan'].setText(data['source']['plan_ref']);c['detail'].setText(data['source']['detail_ref'])
   def choose(attempt=0):
    f=_qt.activeModalWidget()
    try:
     assert isinstance(f,QFileDialog)
     if attempt==0:f.setDirectory(str(tmp_path))
     if attempt in (0,2):
      edit=f.findChild(QLineEdit,'fileNameEdit');edit.setFocus();QTest.keyClick(edit,Qt.Key_A,Qt.ControlModifier);QTest.keyClicks(edit,'detail.json')
     button=f.findChild(QDialogButtonBox).button(QDialogButtonBox.Open)
     if not button.isEnabled() and attempt<50:
      QTimer.singleShot(20,lambda:choose(attempt+1));return
     assert button.isEnabled()
     QTest.mouseClick(f.findChild(QDialogButtonBox).button(QDialogButtonBox.Open),Qt.LeftButton)
    except Exception as exc:
     errors.append(repr(exc))
     if f:f.reject()
   QTimer.singleShot(30,choose);click(c['import_detail'])
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
