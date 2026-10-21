"""Bounded real Qt/source acceptance; synthetic drawing is never a design approval."""
import os,sys,subprocess,json
from pathlib import Path
import pytest

def test_real_main_menu_rtl_ribbon_date_sizes_and_manual_dialog(tmp_path):
 script=Path(__file__).with_name('phase1_final_desktop_probe.py')
 p=subprocess.run([sys.executable,str(script),str(tmp_path)],cwd=script.parents[1],env={**os.environ,'QT_QPA_PLATFORM':os.environ.get('QT_QPA_PLATFORM','offscreen'),'PYTHONFAULTHANDLER':'1'},capture_output=True,text=True,timeout=60)
 assert p.returncode==0,p.stdout+p.stderr
 assert json.loads((tmp_path/'ui-result.json').read_text())['manual_menu']==['manual_from_main_menu']


def test_real_drawing_zoom_region_highlight_calibration_and_persistence(tmp_path,monkeypatch):
 from PySide6.QtCore import Qt,QPoint,QPointF,QEvent,QCoreApplication
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QMessageBox
 from app.graphical_takeoff import GraphicalTakeoffDialog
 from drawing_source_fixture import vector_pdf
 from core.platform.application import StructuralProApp
 global _qt
 _qt=QApplication.instance() or QApplication([]);_qt.setLayoutDirection(Qt.RightToLeft)
 service=StructuralProApp(tmp_path/'db');service.create_project('نقشه برداری مصنوعی نرم‌افزار','DRAW')
 path=vector_pdf(tmp_path);messages=[]
 monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m,*a:messages.append(m))
 d=GraphicalTakeoffDialog(pdf_path=path,app_service=service,project_id='DRAW');d.show();_qt.processEvents()
 try:
  assert d.viewer.kind=='pdf' and d.engine
  assert d.height()<=1000,'Beam controls must scroll instead of forcing the drawing window below the screen'
  original=d.canvas.transform().m11();QTest.mouseClick(d.zoom_in,Qt.LeftButton);assert d.canvas.transform().m11()>original
  QTest.mouseClick(d.zoom_window,Qt.LeftButton)
  view=d.canvas.viewport();bounds=d.canvas.scene.sceneRect();a=d.canvas.mapFromScene(QPointF(bounds.left()+bounds.width()*.2,bounds.top()+bounds.height()*.2));b=d.canvas.mapFromScene(QPointF(bounds.left()+bounds.width()*.6,bounds.top()+bounds.height()*.6))
  QTest.mousePress(view,Qt.LeftButton,pos=a);QTest.mouseMove(view,b,20);QTest.mouseRelease(view,Qt.LeftButton,pos=b)
  assert d.canvas._selected_region_rect is not None and d.canvas._region_overlay is not None
  assert d.grab().save(str(tmp_path/'drawing-highlight.png'))
  QTest.mouseClick(d.region_to_takeoff,Qt.LeftButton)
  assert messages and 'کالیبر' in messages[-1] and not d.session.items
  d.session.calibrate(1,100,10)
  from core.drawings.graphical_takeoff import Point
  item=d.session.add_area([Point(0,0),Point(100,0),Point(100,50),Point(0,50)],page=1,label='سطح مصنوعی ۵۰ مترمربع',source='synthetic:explicit-rectangle',takeoff_code='SYN-AREA')
  assert item.quantity==50;d.refresh();QTest.mouseClick(d.save_session_button,Qt.LeftButton)
  assert d.persisted_session_id and not service.open_project('DRAW')['boq']
  sid=d.persisted_session_id
  with pytest.raises(RuntimeError):service.save_drawing_takeoff_session('DRAW',d.session,session_id=sid,expected_revision=0)
  d.close();service.store.close();service=StructuralProApp(tmp_path/'db')
  saved=service.load_drawing_takeoff_session('DRAW',sid)
  assert saved['session']['items'][0]['quantity']==50
  assert not service.open_project('DRAW')['boq']
 finally:
  d.close();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);_qt.processEvents();service.store.close()
