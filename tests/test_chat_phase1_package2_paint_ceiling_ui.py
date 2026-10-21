"""Phase 1 package 2: real Qt editor integration with existing approved synthetic fixtures."""
from copy import deepcopy
import pytest

@pytest.mark.parametrize("kind,sample_module",[
 ("paint_finish","test_paint_finish_phase1"),
 ("suspended_ceiling","test_suspended_ceiling_phase1"),
])
def test_specialist_persian_form_load_preview_and_fail_closed(tmp_path,monkeypatch,kind,sample_module):
 from importlib import import_module
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtWidgets import QApplication,QMessageBox,QTableWidgetItem
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.architecture_detail_editor import open_architecture_editor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 app=StructuralProApp(tmp_path/"db");app.create_project("مصنوعی","P")
 original=import_module(sample_module).sample()
 app.save_aec_system_draft("P",deepcopy(original),expected_revision=0)
 warnings=[];errors=[]
 monkeypatch.setattr(QMessageBox,"warning",lambda _parent,_title,message: warnings.append(str(message)))
 def click(c,name):
  tab=c["tabs"]
  for i in range(tab.count()):
   if tab.widget(i).isAncestorOf(c[name]):tab.setCurrentIndex(i);break
  QTest.mouseClick(c[name],Qt.LeftButton);_qt.processEvents()
 def run():
  d=_qt.activeModalWidget();c=d.architecture_controls
  try:
   c["id"].setText(original["system_id"])
   click(c,"load")
   assert not warnings,warnings
   assert d.layoutDirection()==Qt.RightToLeft
   assert c["kind"].currentData()==kind
   assert c["special_groups"] and c["special_tables"]
   assert all(c["special_tables"][name].rowCount()==len(original["architecture_detail"][
    "stages" if kind=="paint_finish" else "groups"][name][
    "passes" if kind=="paint_finish" else "items"]) for name in c["special_tables"])
   click(c,"preview")
   assert "محاسبه معتبر" in c["message"].text(),(kind,warnings,c["message"].text())
   assert c["grid"].rowCount()>0
   before=deepcopy(app.open_project("P"))
   if kind=="paint_finish":
    table=c["tables"]["zones"]
    col=[k for k,_ in c["columns"]["zones"]].index("opening_ids")
    assert table.item(0,col).text()=='["O1"]'
    table.setItem(0,col,QTableWidgetItem("not-json"))
   else:
    table=c["special_tables"]["panels"]
    col=[k for k,_ in c["special_columns"]["panels"]].index("width_m")
    table.setItem(0,col,QTableWidgetItem("999"))
   click(c,"preview")
   assert warnings or "خارج" in c["message"].text() or "بازشو" in c["message"].text()
   assert app.open_project("P")==before
  except Exception as exc:
   errors.append(repr(exc))
  finally:
   d.reject()
 QTimer.singleShot(40,run)
 open_architecture_editor(app,project_id="P",floor_id="L1",kind=kind)
 app.store.close()
 assert not errors,errors

@pytest.mark.parametrize("kind,sample_module",[
 ("paint_finish","test_paint_finish_phase1"),
 ("suspended_ceiling","test_suspended_ceiling_phase1"),
])
def test_new_specialist_never_generates_unverified_quantities(tmp_path,monkeypatch,kind,sample_module):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtWidgets import QApplication,QMessageBox
 from PySide6.QtTest import QTest
 from core.platform.application import StructuralProApp
 from app.architecture_detail_editor import open_architecture_editor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 app=StructuralProApp(tmp_path/"db");app.create_project("مصنوعی","P")
 errors=[];warnings=[]
 monkeypatch.setattr(QMessageBox,"warning",lambda p,t,m:warnings.append(str(m)))
 def run():
  d=_qt.activeModalWidget();c=d.architecture_controls
  try:
   c["id"].setText("NEW")
   QTest.mouseClick(c["new"],Qt.LeftButton)
   assert c["special_groups"]
   assert all(group["status"].currentData()=="unreviewed" for group in c["special_groups"].values())
   assert all(t.rowCount()==0 for t in c["special_tables"].values())
   c["tabs"].setCurrentIndex(c["tabs"].count()-1)
   QTest.mouseClick(c["preview"],Qt.LeftButton)
   assert c["grid"].rowCount()==0
   assert not app.open_project("P")["boq"]
  except Exception as exc:errors.append(repr(exc))
  finally:d.reject()
 QTimer.singleShot(30,run)
 open_architecture_editor(app,project_id="P",floor_id="L1",kind=kind)
 app.store.close()
 assert not errors,errors
