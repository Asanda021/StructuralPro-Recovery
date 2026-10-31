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
        assert not result["source_preflight_clear"]
        assert result["final_commit_authority"] is False
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
        with pytest.raises(ValueError, match="مهندس"):
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
        assert not result["source_preflight_clear"]
    finally:
        app.store.close()


def test_distinct_real_floor_member_does_not_invent_conflict(tmp_path):
    app, project, args, _, _ = _two_sessions(tmp_path, member="P2")
    try:
        result = require_no_pending_source_discrepancies(app, **args)
        assert result["status"] == "NO_CROSS_SESSION_MEMBER_CONFLICT_FOUND"
        assert result["source_preflight_clear"]
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


def _ai_area_history(tmp_path):
    """Stored AI proposal from the real vector-PDF session and SQLite."""
    app, _, _, _ = fixture(tmp_path)
    session, original, old = polygon(app, tmp_path / "plan.pdf")
    proposal = {
        "drawing_id": old["session_id"],
        "revision_id": str(old["revision"]),
        "candidates": [{
            "source_id": "page-1:area-approved-by-reviewer",
            "session_item_id": original.id,
            "page": 1,
            "kind": "area",
            "unit": "m2",
            "quantity": original.quantity,
            "confidence": 0.98,
            "label": "سطح PDF به تأیید انسانی رسیده",
            "formula": original.formula,
            "evidence": {
                "source_ref": original.source_ref,
                "scale_ref": "calibration:page-1",
                "meters_per_pixel": session.calibrations[1].meters_per_pixel,
            },
        }],
    }
    app.commit_ai_takeoff_proposal("P", proposal, user_confirmed=True)
    _, candidate, pending = polygon(app, tmp_path / "plan.pdf")
    current = app.open_project("P")
    args = {
        "project_id": "P",
        "expected_project_version": current["_meta"]["version"],
        "session_id": pending["session_id"],
        "selected_item_ids": (candidate.id,),
    }
    return app, current, args


def test_historical_ai_area_requires_original_member_evidence(tmp_path):
    app, snapshot, opts = _ai_area_history(tmp_path)
    digest = app.store.current_digest("P")
    try:
        result = inspect_pending_source_discrepancies(app, **opts)
        assert result["status"] == "REVIEW_REQUIRED"
        assert result["source_preflight_clear"] is False
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["committed"]["source_mode"] == "drawing_ai"
        assert result["conflicts"][0]["committed"]["member_id"] == "P1"
        assert result["conflicts"][0]["code"] == "POTENTIAL_DUPLICATE_MEMBER_SOURCE"
        with pytest.raises(ValueError, match="مهندس"):
            require_no_pending_source_discrepancies(app, **opts)
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == snapshot
    finally:
        app.store.close()


def test_historical_ai_invalid_identity_fails_closed_even_if_boq_looks_normal(tmp_path, monkeypatch):
    app, snapshot, opts = _ai_area_history(tmp_path)
    original_open = app.open_project

    def corrupt_cached_read(pid):
        project = deepcopy(original_open(pid))
        ai = next(r for r in project["takeoffs"] if r["domain"] == "drawing_ai")
        ai["params"]["measurement_identity"] = "spoofed-measurement"
        return project

    monkeypatch.setattr(app, "open_project", corrupt_cached_read)
    try:
        with pytest.raises(ValueError):
            inspect_pending_source_discrepancies(app, **opts)
    finally:
        app.store.close()
