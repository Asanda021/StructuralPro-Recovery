"""P7 P5 E8: real persisted PDF sessions, verified member identities and BOQ."""
from copy import deepcopy
from decimal import Decimal

import pytest

from test_phase2_pdf_roof import fixture
from test_phase2_advanced_geometry_sqlite import polygon, P
from core.reports.source_discrepancy_gate import (
    inspect_pending_source_discrepancies,
    require_no_pending_source_discrepancies,
)


def _two_sessions(tmp_path, *, points=P, member="P1"):
    app, _, _, _ = fixture(tmp_path)
    original, item, old = polygon(app, tmp_path / "plan.pdf")
    app.commit_drawing_takeoff_to_boq(
        "P", old["session_id"], [item.id],
        expected_session_revision=old["revision"],
    )
    _, candidate, pending = polygon(
        app, tmp_path / "plan.pdf", points=points, member=member)
    snapshot = app.open_project("P")
    args = {
        "project_id": "P",
        "expected_project_version": snapshot["_meta"]["version"],
        "session_id": pending["session_id"],
        "selected_item_ids": (candidate.id,),
    }
    return app, snapshot, args, old, pending


def test_same_reviewed_member_and_quantity_is_review_only_not_auto_approved(tmp_path):
    app, project, args, old, pending = _two_sessions(tmp_path)
    try:
        digest = app.store.current_digest("P")
        before = deepcopy(project)
        result = inspect_pending_source_discrepancies(app, **args)
        assert result["status"] == "REVIEW_REQUIRED"
        assert not result["allowed_to_commit"]
        assert not result["approved_for_engineering_release"]
        assert not result["mutation"]
        assert len(result["conflicts"]) == 1
        conflict = result["conflicts"][0]
        assert conflict["code"] == "POTENTIAL_DUPLICATE_MEMBER_SOURCE"
        assert conflict["committed"]["quantity"] == conflict["candidate"]["quantity"]
        assert conflict["candidate"]["member_id"] == "P1"
        assert conflict["candidate"]["floor_id"] == "L1"
        assert conflict["committed"]["source_id"] != conflict["candidate"]["source_id"]
        assert conflict["candidate"]["source_sha256"] == project["drawing_sessions"][args["session_id"]]["source_sha256"]
        with pytest.raises(ValueError, match="بازبینی"):
            require_no_pending_source_discrepancies(app, **args)
        assert digest == app.store.current_digest("P")
        assert before == app.open_project("P")
    finally:
        app.store.close()


def test_same_member_different_measured_quantity_blocks_without_guessing(tmp_path):
    changed = [(100,100),(600,100),(600,400),(100,400)]
    app, project, args, _, _ = _two_sessions(tmp_path, points=changed)
    try:
        result = inspect_pending_source_discrepancies(app, **args)
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["code"] == "MEMBER_SOURCE_QUANTITY_DISCREPANCY"
        assert Decimal(result["conflicts"][0]["candidate"]["quantity"]) != Decimal(result["conflicts"][0]["committed"]["quantity"])
        assert not result["allowed_to_commit"]
    finally:
        app.store.close()


def test_distinct_real_floor_member_does_not_invent_conflict(tmp_path):
    app, project, args, _, _ = _two_sessions(tmp_path, member="P2")
    try:
        result = require_no_pending_source_discrepancies(app, **args)
        assert result["status"] == "NO_CROSS_SESSION_MEMBER_CONFLICT_FOUND"
        assert result["allowed_to_commit"]
        assert not result["approved_for_engineering_release"]
        assert result["conflicts"] == []
    finally:
        app.store.close()


def test_stale_project_and_mutated_source_are_rejected(tmp_path):
    app, project, args, _, _ = _two_sessions(tmp_path)
    try:
        with pytest.raises(ValueError, match="نسخه"):
            inspect_pending_source_discrepancies(
                app, **(args | {"expected_project_version": args["expected_project_version"] - 1}))
        path = tmp_path / "plan.pdf"
        path.write_bytes(path.read_bytes() + b"changed original source")
        with pytest.raises(ValueError):
            inspect_pending_source_discrepancies(app, **args)
    finally:
        app.store.close()


@pytest.mark.parametrize("selected", [(), ("UNKNOWN",), ("TO-00001", "TO-00001")])
def test_selection_missing_or_duplicate_is_rejected(tmp_path, selected):
    app, project, args, _, _ = _two_sessions(tmp_path)
    try:
        with pytest.raises(ValueError):
            inspect_pending_source_discrepancies(
                app, **(args | {"selected_item_ids": selected}))
    finally:
        app.store.close()


def test_nonexistent_persisted_session_must_not_pass(tmp_path):
    app, project, args, _, _ = _two_sessions(tmp_path)
    try:
        with pytest.raises(ValueError):
            inspect_pending_source_discrepancies(app, **(args | {"session_id": "fabricated"}))
    finally:
        app.store.close()
