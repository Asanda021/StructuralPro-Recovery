"""Real offscreen Qt interaction with current SQLite, no fake approval."""
def test_aec_navigation_and_readonly_preflight(tmp_path,monkeypatch):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QFileDialog,QPushButton,QMessageBox
 from core.platform.application import StructuralProApp
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 from test_structural_handoff_work import request,evidence
 global _qt
 _qt=QApplication.instance() or QApplication([])
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');p,h=evidence(tmp_path,request());errors=[]
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(p),''))
 warnings=[]
 # Existing generic editor calls load() before a member ID is entered.
 # Capture that native modal while still exercising the real child dialog.
 monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m,*_:warnings.append(str(m)))
 def run():
  parent=_qt.activeModalWidget()
  def child():
   dlg=_qt.activeModalWidget()
   try:
    c=dlg.handoff_controls;assert dlg.layoutDirection()==Qt.RightToLeft
    assert not c['source_path'].text() and not c['source_sha256'].text()
    QTest.mouseClick(c['load'],Qt.LeftButton);QTest.mouseClick(c['preview'],Qt.LeftButton)
    assert c['rows'].rowCount()==66 and 'مسدود' in c['message'].text()
    assert c['source_sha256'].text()==h and not a.open_project('P')['boq']
    assert c['result']['commit_allowed'] is False
    assert not any('ثبت قطعی' in b.text() for b in dlg.findChildren(QPushButton))
    c['payload'].setPlainText('{invalid');QTest.mouseClick(c['preview'],Qt.LeftButton)
    assert c['rows'].rowCount()==0 and c['result'] is None and 'خطا' in c['message'].text()
    QTest.mouseClick(c['clear'],Qt.LeftButton);assert not c['payload'].toPlainText() and not c['source_path'].text()
    QTest.mouseClick(c['close'],Qt.LeftButton)
   except Exception as exc:errors.append(repr(exc));dlg.reject()
  try:
   QTimer.singleShot(30,child);QTest.mouseClick(parent.structural_handoff_button,Qt.LeftButton)
  except Exception as exc:errors.append(repr(exc))
  finally:parent.reject()
 QTimer.singleShot(30,run);open_reviewed_aec_editor(a,project_id='P',floor_id='L1');a.store.close();assert not errors,errors
 assert warnings==['پروژه، طبقه، نوع سیستم و شناسه عضو باید مشخص شوند']
