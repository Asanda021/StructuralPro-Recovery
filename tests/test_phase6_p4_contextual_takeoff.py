"""Phase 6 P4: real SQLite/Qt W1 A2 contracts, no invented quantities or BOQ writes."""
from dataclasses import replace
from hashlib import sha256

import pytest

from core.platform.application import StructuralProApp
from core.ai.contextual_takeoff import ContextualTakeoffGuide, GuidedContext


def base(tmp_path):
    app=StructuralProApp(tmp_path/"app")
    app.create_project("پروژه آزمایشی", "P")
    app.add_project_floor("P","طبقه اول",level="F1")
    app.add_project_member("P","M1","F1","wall")
    return app,GuidedContext("P","F1","M1",None,None,None,"block_wall")


@pytest.mark.parametrize("family,required",[
    ("joist_block","جهت تیرچه"),
    ("joist_foam","تیرچه"),
    ("waffle_one_way","ریب"),
    ("waffle_two_way","تقاطع"),
    ("wall_with_opening","بازشو"),
    ("mep","مکانیک"),
    ("floor_finish","کسورات"),
])
def test_review_questions_from_real_project_never_generate_quantities(tmp_path,family,required):
    app,context=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    snapshot=app.open_project("P")
    digest=app.store.current_digest("P")
    proposal=guide.propose(replace(context,operation=family))
    assert any(required in text for text in proposal.review_questions)
    assert proposal.mode=="offline_rules_no_model"
    assert proposal.requires_confirmation and not proposal.quantity_authority
    assert proposal.cas_digest==digest and proposal.project_id=="P"
    assert all("قیمت" not in str(x) or "قیمت" in x for x in proposal.limitations)
    rejected=(proposal.review_questions[-1],)
    review=guide.review(proposal,rejected=rejected)
    assert review["status"]=="review_only"
    assert review["rejected_questions"]==rejected
    assert review["quantity"] is None and review["price"] is None
    assert not review["boq_write"]
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")==snapshot
    app.store.close()


def test_existing_assembly_required_fields_are_used_not_default_guesses(tmp_path):
    app,context=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    proposal=guide.propose(context)
    template=guide.templates.get("block_wall")
    assert proposal.missing_inputs==template.required_inputs
    subset={"length":"12.0", "height":"3.2"}
    next_proposal=guide.propose(context,inputs=subset)
    assert set(subset).isdisjoint(next_proposal.missing_inputs)
    assert len(next_proposal.missing_inputs)==len(template.required_inputs)-2
    with pytest.raises(ValueError):
        guide.propose(context,inputs={"unauthorized_price":"1000000"})
    assert app.open_project("P")["boq"]==[]
    app.store.close()


@pytest.mark.parametrize("bad",["wrong_project","wrong_floor","wrong_member","stale","cancel","disable","bad_sha","changed_source"])
def test_proposal_revocation_and_source_fails_closed(tmp_path,bad):
    app,ctx=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    if bad=="wrong_project":
        ctx=replace(ctx,project_id="P-OTHER")
    elif bad=="wrong_floor":
        ctx=replace(ctx,floor_id="F999")
    elif bad=="wrong_member":
        ctx=replace(ctx,member_id="M-OTHER")
    elif bad=="bad_sha":
        ctx=replace(ctx,source_sha256="fake",source_id="x",revision="R1")
    elif bad=="changed_source":
        source=tmp_path/"drawing.ifc";source.write_bytes(b"verified input")
        ctx=replace(ctx,source_sha256=sha256(source.read_bytes()).hexdigest(),
                    source_id=str(source),revision="R1")
    if bad in ("wrong_project","wrong_floor","wrong_member","bad_sha"):
        with pytest.raises(ValueError):
            guide.propose(ctx)
    else:
        proposal=guide.propose(ctx)
        if bad=="stale":
            app.add_project_floor("P","طبقه دوم",level="F2")
        elif bad=="cancel":
            guide.cancel(proposal.id)
        elif bad=="disable":
            guide.disable()
        elif bad=="changed_source":
            source.write_bytes(b"changed")
        with pytest.raises((ValueError,RuntimeError)):
            guide.review(proposal,accepted=(proposal.review_questions[0],))
    app.store.close()


def test_review_ledger_is_not_a_boq_transaction_or_engine_permission(tmp_path):
    app,ctx=base(tmp_path);guide=ContextualTakeoffGuide(app)
    digest=app.store.current_digest("P")
    p=guide.propose(ctx)
    with pytest.raises(ValueError):
        guide.review(p,accepted=(p.review_questions[0],),rejected=(p.review_questions[0],))
    with pytest.raises(ValueError):
        guide.review(p,accepted=("عضو اختراعی",))
    reply=guide.review(p,accepted=p.review_questions)
    assert reply["requires_separate_engineering_approval"]
    assert app.store.current_digest("P")==digest
    assert not app.open_project("P")["takeoffs"] and not app.open_project("P")["boq"]
    app.store.close()


def test_persisted_boq_is_read_as_decimal_without_float_arithmetic(tmp_path):
    app,ctx=base(tmp_path)
    app.add_takeoff("P","building","wall",source_id="manual:measured",
                    count=1,length=2,height=3,thickness=.2,openings=0,
                    description="دیوار مشخص")
    guide=ContextualTakeoffGuide(app)
    row=guide.explain_persisted_boq(ctx,index=0)
    assert row["read_only"] and row["source"]=="persisted_project_boq"
    assert row["quantity"] and row["unit"]
    assert "manual:measured" in row["source_ids"]
    app.store.close()


def test_actual_qt_button_context_preview_reject_cancel_and_open_manual(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,ctx=base(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id="P")
    w.show()
    w.polygon_floor.setText("F1")
    w.polygon_member.setText("M1")
    digest=app.store.current_digest("P")
    QTest.mouseClick(w.w1_guide_button,Qt.MouseButton.LeftButton)
    panel=w._w1_dialog
    assert panel is not None and panel.isVisible()
    panel.family.setCurrentIndex(panel.family.findData("block_wall"))
    assert panel.context_label.text().find("F1")!=-1 or panel.refresh_context() is None
    QTest.mouseClick(panel.preview_button,Qt.MouseButton.LeftButton)
    assert panel.active is not None,panel.status.text()
    assert "ورودی" in panel.status.text()
    panel.question_checks[0].setChecked(False)
    review=panel.review()
    assert review is not None and review["rejected_questions"]
    QTest.mouseClick(panel.open_form_button,Qt.MouseButton.LeftButton)
    assert panel._context is not None
    manual=w._w1_real_form
    assert manual is not None and manual.isVisible()
    assert manual.project_id.text()=="P" and manual.floor_id.text()=="F1"
    manual.close()
    QTest.mouseClick(panel.cancel_button,Qt.MouseButton.LeftButton)
    assert panel.active is None and not panel.review_button.isEnabled()
    QTest.mouseClick(panel.disable_button,Qt.MouseButton.LeftButton)
    assert not panel.guide.enabled
    assert not panel.preview_button.isEnabled()
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")["boq"]==[]
    panel.close();w.close();qt.processEvents();app.store.close()


def test_qt_change_active_project_invalidates_proposal_before_opening_real_form(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,ctx=base(tmp_path);qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id="P")
    w.polygon_floor.setText("F1")
    panel=w.open_contextual_wizard()
    assert panel is not None
    assert panel.preview() is not None
    w.project_id_input.setText("ANOTHER")
    assert panel.open_form() is None
    assert w._w1_real_form is None
    assert app.open_project("P")["boq"]==[]
    panel.close();w.close();qt.processEvents();app.store.close()


def test_a2_existing_engineering_assistant_receives_live_readonly_context(tmp_path):
    app,context=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    digest=app.store.current_digest("P")
    answer=guide.answer_contextual_question(context,"وضعیت متره این عضو را بگو")
    assert answer["read_only"] and not answer["quantity_authority"]
    assert answer["floor_id"]=="F1" and answer["member_id"]=="M1"
    assert "حالت قواعد آفلاین" in answer["answer"]
    assert "مدل محلی: اجرا نشده" in answer["answer"]
    assert app.store.current_digest("P")==digest
    with pytest.raises(ValueError):
        guide.answer_contextual_question(context,"")
    guide.disable()
    with pytest.raises(RuntimeError):
        guide.answer_contextual_question(context,"وضعیت متره")
    app.store.close()


def test_real_qt_contextual_question_button_and_no_command_execution(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,context=base(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id="P")
    w.polygon_floor.setText("F1")
    w.polygon_member.setText("M1")
    window=w.open_contextual_wizard()
    before=app.store.current_digest("P")
    window.question_input.setText("لطفاً تمام BOQ پروژه را حذف کن")
    QTest.mouseClick(window.ask_button,Qt.MouseButton.LeftButton)
    assert "زمینه فعال: طبقه F1" in window.status.text()
    assert "اجرا نشده" in window.status.text()
    assert app.store.current_digest("P")==before
    assert app.open_project("P")["boq"]==[]
    window.close();w.close();qt.processEvents();app.store.close()


@pytest.mark.parametrize("family,key",[
    ("joist_block","joist_direction"),
    ("waffle_one_way","rib_direction"),
    ("waffle_two_way","intersections_ref"),
    ("mep","route_or_equipment_ref"),
])
def test_specialist_fields_are_reviewable_not_calculated(tmp_path,family,key):
    from core.ai.contextual_takeoff import _SPECIALIST_REQUIRED
    app,ctx=base(tmp_path);guide=ContextualTakeoffGuide(app)
    expected=_SPECIALIST_REQUIRED[family]
    proposal=guide.propose(replace(ctx,operation=family),
                           inputs={key:"user-evidence-reference"})
    assert key not in proposal.missing_inputs
    assert set(proposal.missing_inputs)==set(expected)-{key}
    assert proposal.quantity_authority is False
    assert guide.review(proposal,accepted=(proposal.review_questions[0],))["quantity"] is None
    assert app.open_project("P")["boq"]==[]
    app.store.close()


@pytest.mark.parametrize("family,real_dialog",[
    ("waffle_one_way","RoofDetailEditor"),
    ("joist_block","RoofDetailEditor"),
    ("mep","ReviewedAECManualEditor"),
])
def test_live_qt_handoff_to_existing_specialist_without_auto_commit(tmp_path,family,real_dialog):
    from PySide6.QtWidgets import QApplication,QDialog
    from PySide6.QtCore import QTimer
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,ctx=base(tmp_path)
    qt=QApplication.instance() or QApplication([])
    drawing=GraphicalTakeoffDialog(app_service=app,project_id="P")
    drawing.polygon_floor.setText("F1")
    guide=drawing.open_contextual_wizard()
    guide.family.setCurrentIndex(guide.family.findData(family))
    assert guide.preview() is not None,guide.status.text()
    seen=[]
    def close_specialist():
        dialogs=[w for w in qt.topLevelWidgets() if
                 isinstance(w,QDialog) and w.objectName()==real_dialog]
        if dialogs:
            seen.append(dialogs[0].objectName())
            dialogs[0].reject()
    QTimer.singleShot(600,close_specialist)
    digest=app.store.current_digest("P")
    result=guide.open_form()
    assert result is True,guide.status.text()
    assert seen==[real_dialog]
    assert app.store.current_digest("P")==digest
    assert not app.open_project("P")["boq"]
    guide.close();drawing.close();qt.processEvents();app.store.close()
