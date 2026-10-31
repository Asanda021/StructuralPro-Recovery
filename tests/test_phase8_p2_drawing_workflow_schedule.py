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
    finally:
        panel.close()
