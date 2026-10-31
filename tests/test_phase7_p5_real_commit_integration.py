"""Phase7 P5: mandatory E8 checks in the real manual BOQ save workflow.

Use actual SQLite, vector PDF and source-pinned sessions; no synthetic
in-memory fake BOQ or alternate commit engine.
"""
from copy import deepcopy
import pytest

from test_phase7_p5_source_discrepancy_gate import _two_sessions
from core.reports import source_discrepancy_gate


def test_real_manual_commit_cannot_transfer_changed_member_without_review(tmp_path):
    changed = [(100,100),(600,100),(600,400),(100,400)]
    app, project, args, _, pending = _two_sessions(tmp_path, points=changed)
    before = deepcopy(project)
    digest = app.store.current_digest("P")
    try:
        with pytest.raises(ValueError):
            app.commit_drawing_takeoff_to_boq(
                "P", args["session_id"], list(args["selected_item_ids"]),
                expected_session_revision=pending["revision"],
            )
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()


def test_manual_commit_path_invokes_e8_and_keeps_atomicity_on_review_gate(tmp_path,monkeypatch):
    # A new, nonconflicting member is normally accepted. Test proves the
    # application actually invokes the E8 source gate before any DB write.
    app, project, args, _, pending = _two_sessions(tmp_path, member="P2", points=[(600,100),(800,100),(800,600),(600,600)])
    original = deepcopy(project)
    digest = app.store.current_digest("P")
    called = []
    def independent_gate(service, **kwargs):
        called.append(kwargs)
        raise ValueError("E8 review needed")
    monkeypatch.setattr(source_discrepancy_gate, "require_no_pending_source_discrepancies", independent_gate)
    try:
        with pytest.raises(ValueError, match="E8 review needed"):
            app.commit_drawing_takeoff_to_boq(
                "P", args["session_id"], list(args["selected_item_ids"]),
                expected_session_revision=pending["revision"],
            )
        assert len(called) == 1
        assert called[0]["session_id"] == args["session_id"]
        assert called[0]["selected_item_ids"] == args["selected_item_ids"]
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == original
    finally:
        app.store.close()


def test_distinct_member_source_can_still_commit_after_real_e8_preflight(tmp_path):
    app, project, args, _, pending = _two_sessions(tmp_path, member="P2", points=[(600,100),(800,100),(800,600),(600,600)])
    before = app.store.current_digest("P")
    try:
        committed = app.commit_drawing_takeoff_to_boq(
            "P", args["session_id"], list(args["selected_item_ids"]),
            expected_session_revision=pending["revision"],
        )
        current = app.open_project("P")
        # Canonical BOQ may aggregate two legitimate same-code measurements.
        # Count stored takeoffs and preserve both source receipts instead of
        # requiring one BOQ row per source.
        assert len(current["takeoffs"]) == 2
        assert committed["boq_count"] == len(current["boq"]) >= 1
        expected_sources = {row["source_id"] for row in current["takeoffs"]}
        actual_sources = {source for boq in current["boq"] for source in boq.get("source_ids", [])}
        assert expected_sources == actual_sources
        assert app.store.current_digest("P") != before
    finally:
        app.store.close()


def test_confirmed_ai_area_commit_still_obeys_e8(tmp_path, monkeypatch):
    """Explicit AI user approval never waives physical-source review gate."""
    from core.drawings.takeoff_session import DrawingTakeoffSession

    app, project, args, _, pending = _two_sessions(
        tmp_path, member="P2",
        points=[(600,100),(800,100),(800,600),(600,600)])
    receipt = app.load_drawing_takeoff_session("P", args["session_id"])
    session = DrawingTakeoffSession.from_dict(receipt["session"])
    item = session.find(args["selected_item_ids"][0])
    proposal = {
        "drawing_id": args["session_id"],
        "revision_id": str(pending["revision"]),
        "candidates": [{
            "source_id": "page-1:reviewed-area-P2",
            "session_item_id": item.id,
            "page": 1,
            "kind": item.kind,
            "unit": item.unit,
            "quantity": item.quantity,
            "confidence": 0.98,
            "label": "سطح مستقل مستند P2",
            "formula": item.formula,
            "evidence": {
                "source_ref": item.source_ref,
                "scale_ref": "calibration:page-1",
                "meters_per_pixel": session.calibrations[1].meters_per_pixel,
            },
        }],
    }
    called = []
    def independent_gate(service, **kwargs):
        called.append(kwargs)
        raise ValueError("E8 source review needed")
    monkeypatch.setattr(
        source_discrepancy_gate,
        "require_no_pending_source_discrepancies", independent_gate)
    before = deepcopy(project)
    digest = app.store.current_digest("P")
    try:
        with pytest.raises(ValueError, match="E8 source review needed"):
            app.commit_ai_takeoff_proposal(
                "P", proposal, user_confirmed=True,
            )
        assert len(called) == 1
        assert called[0]["selected_item_ids"] == args["selected_item_ids"]
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()
