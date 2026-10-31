"""P8/P2: real drawing-intake interaction and editable linked WBS draft.

Tests do not claim accepted production rates, approved schedules or structural
material conclusions without explicit drawing evidence.
"""
from __future__ import annotations
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from core.drawings.dwg_takeoff import DWGDocument
from core.drawings.workflow_planning import (
    infer_structure, new_workflow_plan, edit_activity, sync_measured_items,
)
from core.drawings.takeoff_session import DrawingTakeoffSession


def test_frame_type_comes_from_explicit_layers_and_text_only():
    source = DWGDocument(
        layers=["A-STR", "CONCRETE FRAME", "BARS"],
        text_labels=["ستون بتنی RC COLUMN"],
    )
    result = infer_structure(source)
    assert result["kind"] == "concrete"
    assert result["confidence"] == "corroborated"
    assert len(result["evidence"]) >= 2
    source.layers = ["A-COLS", "GRID"]
    source.text_labels = ["ستون", "تیر 1", "PLAN"]
    assert infer_structure(source)["kind"] == "unknown"
    source.layers = ["STEEL FRAME", "اسکلت بتنی"]
    result = infer_structure(source)
    assert result["kind"] == "mixed"
    assert result["confidence"] == "ambiguous"


def test_architecture_and_mep_are_opt_in_and_schedule_is_not_a_contract():
    plan = new_workflow_plan(
        drawing_source="building.dwg", source_sha256="sha-test",
        structure="steel", disciplines=["architecture", "mechanical", "electrical"],
        inference={"kind": "steel"},
    )
    by_id = {x["id"]: x for x in plan["tasks"]}
    assert "steel_frame" in by_id
    assert "concrete_frame" not in by_id
    assert "masonry" in by_id and "finishes" in by_id
    assert "rough_mechanical" in by_id and "rough_electrical" in by_id
    assert set(by_id["plaster"]["predecessors"]) == {"rough_mechanical", "rough_electrical"}
    assert "fire" not in by_id and "elevator" not in by_id
    assert plan["status"] == "DRAFT_UNAPPROVED"
    assert plan["calendar"]["start_date"] is None
    assert plan["indicative_total_workdays"] > 0
    assert all(not task["baseline_approved"] for task in plan["tasks"])


def test_ambiguous_and_unassigned_takeoff_never_create_fake_structure_or_date():
    plan = new_workflow_plan(
        drawing_source="plan.dxf", source_sha256="sha",
        structure="unknown", disciplines=[], inference={"kind": "unknown"},
    )
    tasks = {x["id"]: x for x in plan["tasks"]}
    assert tasks["structure_unknown"]["duration_days"] == 0
    assert "concrete_frame" not in tasks and "steel_frame" not in tasks
    session = DrawingTakeoffSession()
    item = session.add_count(2, label="میلگرد")
    sync_measured_items(plan, [item])
    assert plan["unassigned_item_ids"] == [item.id]
    assert not any(t["linked_item_ids"] for t in plan["tasks"])


def test_live_measurement_links_and_user_edits_survive_undo_round_trip():
    session = DrawingTakeoffSession()
    plan = new_workflow_plan(
        drawing_source=session.drawing_source, source_sha256=session.source_sha256,
        structure="concrete", disciplines=["architecture"],
    )
    plan = edit_activity(plan, "masonry", duration_days=17,
                         crew="اکیپ دیوارچینی", predecessors=["slabs"])
    session.workflow_plan = plan
    first = session.add_count(12, label="دیوار بلوکی", takeoff_code="WALL")
    sync_measured_items(plan, session.items)
    by_id = {x["id"]: x for x in plan["tasks"]}
    assert by_id["masonry"]["linked_item_ids"] == [first.id]
    assert by_id["masonry"]["duration_days"] == 17
    assert by_id["masonry"]["crew"] == "اکیپ دیوارچینی"
    assert by_id["masonry"]["quantity_reviewed"] is False
    session.add_count(2, label="کابل برق")
    sync_measured_items(plan, session.items)
    assert len(plan["unassigned_item_ids"]) == 1
    assert by_id["masonry"]["duration_days"] == 17
    restored = DrawingTakeoffSession.from_dict(session.to_dict())
    assert restored.workflow_plan["tasks"][
        next(i for i,t in enumerate(restored.workflow_plan["tasks"]) if t["id"] == "masonry")
    ]["duration_days"] == 17
    assert len(restored.workflow_plan["unassigned_item_ids"]) == 1


def test_schedule_rejects_cycles_unknown_predecessors_bad_duration():
    plan = new_workflow_plan(drawing_source="p.dwg", source_sha256="x",
                             structure="concrete", disciplines=["architecture"])
    for invalid in ({"duration_days": -1}, {"duration_days": 1.1},
                    {"predecessors": ["nonexistent"]},
                    {"predecessors": ["handover"]}):
        with pytest.raises(ValueError):
            edit_activity(plan, "mobilize", **invalid)
    assert next(x for x in plan["tasks"] if x["id"] == "mobilize")["duration_days"] == 3


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(["StructuralPro drawing workflow CI"])
    return app


def test_real_qt_intake_choices_and_schedule_editor(qapp):
    from app.drawing_workflow_dialog import DrawingWorkflowIntakeDialog, DrawingScheduleDialog
    evidence = infer_structure(DWGDocument(layers=["STEEL FRAME"], text_labels=["STEEL COLUMN"]))
    intake = DrawingWorkflowIntakeDialog("building.dwg", evidence)
    try:
        assert intake.frame_kind.currentData() == "steel"
        assert intake.disciplines["architecture"].isChecked() is False
        assert intake.disciplines["mechanical"].isChecked() is False
        intake.disciplines["architecture"].setChecked(True)
        intake.disciplines["mechanical"].setChecked(True)
        assert intake.selection() == ("steel", ["architecture", "mechanical"])
        assert intake.pricing_mode.currentData() is None
        assert intake.automatic_schedule.currentData() is None
    finally:
        intake.close()
    state = [new_workflow_plan(drawing_source="b.dwg", source_sha256="xyz",
                               structure="steel", disciplines=["architecture","mechanical"])]
    def edit(value):
        state[0] = value
    panel = DrawingScheduleDialog(lambda:state[0], edit)
    try:
        row = next(i for i,t in enumerate(state[0]["tasks"]) if t["id"]=="masonry")
        panel.table.item(row, 3).setText("24")
        assert next(x for x in state[0]["tasks"] if x["id"] == "masonry")["duration_days"] == 24
        assert next(x for x in state[0]["tasks"] if x["id"] == "masonry")["duration_edited"]
        assert state[0]["calendar"]["start_date"] is None
        assert panel.gantt_view.objectName()=="DrawingRelativeGantt"
        assert panel.gantt_scene.items()
        # Gantt bars are relative working days; no invented completion dates.
        assert state[0]["status"]=="DRAFT_UNAPPROVED"
    finally:
        panel.close()



def test_actual_graphical_dialog_prompts_after_dxf_open_and_live_schedule_tracks_takeoff(qapp, tmp_path):
    import ezdxf
    from app.graphical_takeoff import GraphicalTakeoffDialog

    path = tmp_path / "real-geometry-concrete-structure.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    doc.layers.new("CONCRETE FRAME")
    model = doc.modelspace()
    model.add_line((0, 0), (2, 4), dxfattribs={"layer": "CONCRETE FRAME"})
    model.add_text("RC COLUMN", dxfattribs={"insert": (1, 2)})
    doc.saveas(path)

    dlg = GraphicalTakeoffDialog()
    try:
        dlg.show()
        dlg.open_drawing(str(path))
        qapp.processEvents()
        intake = dlg._workflow_intake_dialog
        assert intake is not None and intake.isVisible()
        assert intake.frame_kind.currentData() == "concrete"
        intake.disciplines["architecture"].setChecked(True)
        intake.pricing_mode.setCurrentIndex(1)
        intake.automatic_schedule.setCurrentIndex(1)
        intake.begin.click()
        qapp.processEvents()
        plan = dlg.session.workflow_plan
        assert plan is not None
        assert plan["source_sha256"] == dlg.session.source_sha256
        assert plan["structure"] == "concrete"
        assert "architecture" in plan["disciplines"]
        assert dlg.schedule_button.isEnabled()
        schedule = dlg._workflow_schedule_dialog
        assert schedule is not None and schedule.isVisible()

        row = next(i for i,t in enumerate(plan["tasks"]) if t["id"] == "masonry")
        schedule.table.item(row,3).setText("23")
        assert next(t for t in dlg.session.workflow_plan["tasks"] if t["id"] == "masonry")["duration_days"] == 23

        item = dlg.session.add_count(4, label="دیوار بلوکی", source="test-wall")
        dlg.refresh()
        linked = next(t for t in dlg.session.workflow_plan["tasks"] if t["id"] == "masonry")
        assert linked["linked_item_ids"] == [item.id]
        assert linked["duration_days"] == 23
        assert "4 عدد" in schedule.table.item(row,7).text()
        stored = DrawingTakeoffSession.from_dict(dlg.session.to_dict())
        assert stored.workflow_plan["structure"] == "concrete"
        assert next(t for t in stored.workflow_plan["tasks"] if t["id"] == "masonry")["duration_days"] == 23
    finally:
        dlg.close()
        qapp.processEvents()



def test_takeoff_undo_redo_never_reverts_user_schedule_edits():
    session = DrawingTakeoffSession()
    plan = new_workflow_plan(drawing_source="", source_sha256="",
                             structure="concrete", disciplines=["architecture"])
    session.workflow_plan = plan
    first = session.add_count(1, label="دیوار بلوکی")
    session.workflow_plan = edit_activity(
        session.workflow_plan, "masonry", duration_days=29, crew="اکیپ اختصاصی"
    )
    second = session.add_count(3, label="دیوار بلوکی", source="second-wall")
    assert session.undo() is True
    sync_measured_items(session.workflow_plan, session.items)
    masonry = next(t for t in session.workflow_plan["tasks"] if t["id"] == "masonry")
    assert masonry["duration_days"] == 29 and masonry["crew"] == "اکیپ اختصاصی"
    assert masonry["linked_item_ids"] == [first.id]
    assert session.redo() is True
    sync_measured_items(session.workflow_plan, session.items)
    masonry = next(t for t in session.workflow_plan["tasks"] if t["id"] == "masonry")
    assert set(masonry["linked_item_ids"]) == {first.id, second.id}
    assert masonry["duration_days"] == 29



def test_queued_post_open_dialog_never_calls_destroyed_qt_window(qapp, tmp_path, monkeypatch):
    """Regression for GUI close: no stale QTimer popup or deleted-scene access."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from app.graphical_takeoff import GraphicalTakeoffDialog
    import sys
    import ezdxf
    path = tmp_path / "open_then_close.dxf"
    drawing = ezdxf.new("R2018")
    drawing.header["$INSUNITS"] = 6
    drawing.modelspace().add_line((0, 0), (2, 2))
    drawing.saveas(path)
    captured = []
    monkeypatch.setattr(sys, "excepthook", lambda cls, value, tb: captured.append(str(value)))
    widget = GraphicalTakeoffDialog()
    widget.show()
    widget.open_drawing(str(path))
    # Kill the underlying C++ widget while its opening workflow is queued.
    widget.close()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents()
    assert captured == []
