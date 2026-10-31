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
    app, project, args, _, pending = _two_sessions(tmp_path, member="P2")
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
    app, project, args, _, pending = _two_sessions(tmp_path, member="P2")
    before = app.store.current_digest("P")
    try:
        committed = app.commit_drawing_takeoff_to_boq(
            "P", args["session_id"], list(args["selected_item_ids"]),
            expected_session_revision=pending["revision"],
        )
        current = app.open_project("P")
        assert committed["boq_count"] == 2
        assert len(current["takeoffs"]) == 2
        assert len(current["boq"]) == 2
        assert app.store.current_digest("P") != before
    finally:
        app.store.close()
