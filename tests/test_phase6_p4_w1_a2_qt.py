"""Qt click acceptance of stepwise W1 / A2 from drawing and manual workspaces."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from test_phase6_p4_w1_a2_core import case, SLAB


def qt():
    return QApplication.instance() or QApplication([])


def test_real_wizard_all_buttons_missing_inputs_offline_cancel_and_commit(tmp_path,monkeypatch):
    from app.contextual_takeoff_p6 import ContextualTakeoffDialog
    svc=case(tmp_path);app=qt()
    w=ContextualTakeoffDialog(svc,"P");w.show();app.processEvents()
    assert w.windowTitle().startswith("دستیار مرحله‌ای")
    w.floor.setCurrentIndex(w.floor.findData("F1"))
    w.member.setCurrentIndex(w.member.findData("SL1"))
    w.code.setCurrentIndex(w.code.findData("concrete_slab"))
    w.measurement.setText("measured-slab-1")
    before=svc.store.current_digest("P")
    QTest.mouseClick(w.preview_button,Qt.MouseButton.LeftButton)
    assert not w.commit_button.isEnabled() and "openings" in w.preview_text.toPlainText()
    assert w.last_preview.missing
    for k,v in SLAB.items():w.fields[k].setText(v)
    w.approver.setCurrentIndex(w.approver.findData("owner"))
    QTest.mouseClick(w.preview_button,Qt.MouseButton.LeftButton)
    assert w.commit_button.isEnabled()
    assert svc.store.current_digest("P")==before
    w.query.setText("برای دال مقدار بتن چقدر است؟")
    QTest.mouseClick(w.answer_button,Qt.MouseButton.LeftButton)
    assert "عدد" in w.answer_text.text()
    w.offline_enabled.setChecked(False)
    QTest.mouseClick(w.answer_button,Qt.MouseButton.LeftButton)
    assert "غیرفعال" in w.answer_text.text()
    assert svc.store.current_digest("P")==before
    QTest.mouseClick(w.cancel_button,Qt.MouseButton.LeftButton)
    assert not w.commit_button.isEnabled() and w.last_preview is None
    QTest.mouseClick(w.preview_button,Qt.MouseButton.LeftButton)
    assert w.commit_button.isEnabled()
    monkeypatch.setattr(QMessageBox,"question",lambda *args,**kw: QMessageBox.StandardButton.No)
    QTest.mouseClick(w.commit_button,Qt.MouseButton.LeftButton)
    assert svc.store.current_digest("P")==before
    monkeypatch.setattr(QMessageBox,"question",lambda *args,**kw: QMessageBox.StandardButton.Yes)
    QTest.mouseClick(w.commit_button,Qt.MouseButton.LeftButton)
    assert len(svc.open_project("P").get("takeoff_assemblies",[]))==1
    assert not w.commit_button.isEnabled()
    w.close();app.processEvents();svc.store.close()


def test_wizard_rejects_parent_project_switch_without_financial_write(tmp_path):
    from app.contextual_takeoff_p6 import ContextualTakeoffDialog
    svc=case(tmp_path);app=qt()
    current={"project_id":"P"}
    def check():
        if current["project_id"]!="P":raise RuntimeError("پروژه فعال تغییر کرد")
    wizard=ContextualTakeoffDialog(svc,"P",context_guard=check)
    wizard.code.setCurrentIndex(wizard.code.findData("block_wall"))
    current["project_id"]="WRONG"
    assert wizard.preview() is None
    assert "رد شد" in wizard.preview_text.toPlainText()
    assert not svc.open_project("P")["boq"]
    wizard.close();app.processEvents();svc.store.close()


def test_graphical_real_w1_launch_is_working_with_current_project_and_no_drawing(tmp_path):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    svc=case(tmp_path);app=qt()
    w=GraphicalTakeoffDialog(app_service=svc,project_id="P")
    w.show()
    original=svc.store.current_digest("P")
    QTest.mouseClick(w.guided_takeoff_button,Qt.MouseButton.LeftButton)
    wizard=getattr(w,"_p6_takeoff_wizard",None)
    assert wizard is not None and wizard.isVisible()
    assert wizard.pid=="P"
    assert svc.store.current_digest("P")==original
    w.project_id_input.setText("OTHER")
    assert wizard.preview() is None
    wizard.close();w.close();app.processEvents();svc.store.close()


def test_manual_real_w1_launch_and_freetext_member_not_trusted(tmp_path):
    from app.manual_takeoff import ManualTakeoffDialog
    svc=case(tmp_path);app=qt()
    w=ManualTakeoffDialog(svc,"P")
    w.show()
    w.floor_id.setText("F1")
    w.element_label.setText("invented-member")
    QTest.mouseClick(w.contextual_button,Qt.MouseButton.LeftButton)
    wizard=getattr(w,"_p6_wizard",None)
    assert wizard is not None and wizard.floor.currentData()=="F1"
    assert wizard.member.currentData() != "invented-member"
    assert svc.open_project("P")["boq"]==[]
    wizard.close();w.close();app.processEvents();svc.store.close()
