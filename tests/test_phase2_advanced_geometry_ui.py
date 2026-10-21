"""Actual Qt mouse vertices, dialogs, SQLite-facing window; synthetic source."""
from PySide6.QtWidgets import QApplication,QInputDialog,QMessageBox,QDialogButtonBox
from PySide6.QtCore import Qt,QPointF,QTimer
from PySide6.QtTest import QTest
from app.graphical_takeoff import GraphicalTakeoffDialog
from test_phase2_pdf_roof import fixture
_qt=None


def test_polygon_opening_edit_and_navigation_native(tmp_path,monkeypatch,nonblocking_error_dialogs):
 global _qt
 _qt=QApplication.instance() or QApplication([])
 app,_,_,_=fixture(tmp_path);d=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P');d.resize(1500,1100);d.show();_qt.processEvents()
 errors=[]
 def answer():
  w=_qt.activeModalWidget()
  try:
   if isinstance(w,QInputDialog):
    w.setTextValue('O1 synthetic approved opening detail');QTimer.singleShot(20,answer)
    QTest.mouseClick(w.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
   else:
    assert isinstance(w,QMessageBox)
    QTest.mouseClick(w.button(QMessageBox.Yes),Qt.LeftButton)
  except Exception as e:
   errors.append(repr(e))
   if w:w.reject()
 def finish():
  QTimer.singleShot(20,answer);QTest.mouseClick(d.finish,Qt.LeftButton)
  assert not errors,errors
 try:
  assert d.mode.findText('چندضلعی دقیق')>=0
  d.session.calibrate(1,100,1);d.canvas.resetTransform()
  def mode(text):d.mode.setCurrentText(text);_qt.processEvents()
  def points(values):
   for x,y in values:QTest.mouseClick(d.canvas.viewport(),Qt.LeftButton,pos=d.canvas.mapFromScene(QPointF(x,y)))
  mode('چندضلعی دقیق');points([(100,100),(600,100),(600,300),(300,300),(300,600),(100,600)])
  finish()
  assert len(d.session.items)==1 and d.session.items[0].quantity==16
  QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center());mode('بازشوی چندضلعی');points([(150,150),(250,150),(250,250),(150,250)])
  finish()
  assert d.session.items[0].quantity==15 and d.session.items[0].geometry_evidence['opening_refs'], nonblocking_error_dialogs
  QTest.mouseClick(d.undo,Qt.LeftButton);assert d.session.items[0].quantity==16
  QTest.mouseClick(d.redo,Qt.LeftButton);assert d.session.items[0].quantity==15
  QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center());d.highlight_selected_measurement();assert d.canvas._measurement_overlay is not None
  mode('چندضلعی دقیق');points([(200,200),(400,200)])
  QTest.mouseClick(d.back_vertex,Qt.LeftButton);assert len(d.canvas.points)==1
  QTest.mouseClick(d.cancel_polygon,Qt.LeftButton);assert not d.canvas.points
  d.grab().save(str(tmp_path/'advanced-polygon.png'))
 finally:d.close();app.store.close()


def test_rotated_rectangle_native_cancel_edit_save_reopen(tmp_path):
 import json
 from core.platform.application import StructuralProApp
 global _qt
 _qt=QApplication.instance() or QApplication([])
 app,_,_,_=fixture(tmp_path);d=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P');d.resize(1500,1100);d.show();_qt.processEvents();errors=[]
 def confirm(yes):
  def answer():
   w=_qt.activeModalWidget()
   try:QTest.mouseClick(w.button(QMessageBox.Yes if yes else QMessageBox.No),Qt.LeftButton)
   except Exception as e:errors.append(repr(e));w.reject()
  QTimer.singleShot(20,answer);QTest.mouseClick(d.finish,Qt.LeftButton)
 try:
  d.polygon_owner.setText('explicit synthetic owner reference');d.polygon_floor.setText('L1');d.polygon_member.setText('ROT1')
  d.session.calibrate(1,100,1);d.canvas.resetTransform();d.mode.setCurrentText('ناحیه چرخیده')
  points=[(200,100),(400,250),(250,450),(50,300)]
  for x,y in points:QTest.mouseClick(d.canvas.viewport(),Qt.LeftButton,pos=d.canvas.mapFromScene(QPointF(x,y)))
  confirm(False);assert not d.session.items and len(d.canvas.points)==4
  confirm(True);assert d.session.items[0].quantity==6.25
  before=d.session.items[0].geometry
  QTest.mouseClick(d.table.viewport(),Qt.LeftButton,pos=d.table.visualItemRect(d.table.item(0,0)).center())
  def edit():
   w=_qt.activeModalWidget()
   try:
    assert isinstance(w,QInputDialog);w.setTextValue(json.dumps(points[::-1]))
    QTest.mouseClick(w.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok),Qt.LeftButton)
   except Exception as e:errors.append(repr(e));w.reject()
  QTimer.singleShot(20,edit);QTest.mouseClick(d.edit_vertices,Qt.LeftButton)
  assert d.session.items[0].geometry!=before and d.session.items[0].quantity==6.25
  QTest.mouseClick(d.undo,Qt.LeftButton);assert d.session.items[0].geometry==before
  QTest.mouseClick(d.redo,Qt.LeftButton);assert d.session.items[0].quantity==6.25
  QTest.mouseClick(d.save_session_button,Qt.LeftButton);assert d.persisted_session_id
  sid=d.persisted_session_id;expected=d.session.to_dict();assert not errors,errors
  for _ in range(5):
   QTest.mouseClick(d.zoom_in,Qt.LeftButton);QTest.mouseClick(d.zoom_out,Qt.LeftButton)
  QTest.mouseClick(d.pan,Qt.LeftButton);QTest.mouseClick(d.fit,Qt.LeftButton)
  QTest.mouseClick(d.next,Qt.LeftButton);assert d.session.calibration is None
  QTest.mouseClick(d.prev,Qt.LeftButton);assert d.session.items[0].geometry==tuple(tuple(p) for p in points[::-1])
  assert d.session.to_dict()==expected
  d.grab().save(str(tmp_path/'advanced-rotated.png'))
 finally:d.close();app.store.close()
 app=StructuralProApp(tmp_path/'db')
 try:
  stored=app.load_drawing_takeoff_session('P',sid)['session']
  assert json.loads(json.dumps(expected))==stored
 finally:app.store.close()
