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
    import os
    from pathlib import Path
    folder=os.environ.get("STRUCTURALPRO_P6_P4_SCREENSHOT_DIR")
    if folder:
        target=Path(folder);target.mkdir(parents=True,exist_ok=True)
        app.processEvents()
        assert w.grab().save(str(target/"p6-p4-w1-ready-preview.png"))
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
    w.refresh_boq()
    assert w.boq_select.count()>1
    w.boq_select.setCurrentIndex(1)
    w.offline_enabled.setChecked(True)
    w.query.setText("مقدار ردیف ثبت‌شده چقدر است؟")
    QTest.mouseClick(w.answer_button,Qt.MouseButton.LeftButton)
    assert "مقدار دقیق ثبت‌شده" in w.answer_text.text()
    if folder:
        app.processEvents()
        assert w.grab().save(str(target/"p6-p4-a2-authoritative-boq.png"))
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


def test_graphical_actual_region_marks_w1_context_without_guessing_dimensions(tmp_path):
    from PySide6.QtCore import QRectF
    from app.graphical_takeoff import GraphicalTakeoffDialog
    svc=case(tmp_path);app=qt()
    w=GraphicalTakeoffDialog(app_service=svc,project_id="P")
    w.canvas._selected_region_rect=QRectF(10,15,120,85)
    modal=w.open_guided_takeoff()
    assert modal is not None
    assert "ناحیه واقعی" in modal.info.text()
    assert all(not input_.text() for input_ in modal.fields.values())
    assert svc.open_project("P")["boq"]==[]
    modal.close();w.close();app.processEvents();svc.store.close()


def test_waffle_and_hollowcore_buttons_call_real_specialist_entry(tmp_path,monkeypatch):
    from app.contextual_takeoff_p6 import ContextualTakeoffDialog
    import app.roof_detail_editor as roof
    svc=case(tmp_path);app=qt()
    calls=[]
    def open_existing(service, *, parent=None,project_id='',floor_id='',kind='',drawing_source=None):
        calls.append((service,project_id,floor_id,kind))
        return 0
    monkeypatch.setattr(roof,"open_roof_editor",open_existing)
    wizard=ContextualTakeoffDialog(svc,"P")
    wizard.floor.setCurrentIndex(wizard.floor.findData("F1"))
    for code,kind in (("waffle_one_way","waffle_one_way"),
                      ("waffle_two_way","waffle_two_way"),
                      ("hollowcore","hollow_core_detail")):
        wizard.code.setCurrentIndex(wizard.code.findData(code))
        assert wizard.specialist_button.isEnabled()
        QTest.mouseClick(wizard.specialist_button,Qt.MouseButton.LeftButton)
        assert calls[-1]==(svc,"P","F1",kind)
    assert not svc.open_project("P")["boq"]
    wizard.close();app.processEvents();svc.store.close()
