"""Phase 6 revision intelligence regression/integration tests."""
import pytest

from core.revisions.intelligence import (
    apply_change_review,
    boq_revision_impact,
    build_revision_history,
    compare_project_revisions,
    summarize_impact,
    to_rtl_report_rows,
)


def test_all_building_disciplines_share_one_revision_contract():
    before = [
        {"object_id": "W1", "discipline": "architecture", "member_type": "wall", "quantity": 20, "unit": "m2"},
        {"object_id": "S1", "discipline": "structural", "member_type": "steel", "quantity": 10, "unit": "m", "steel_weight_kg": 500},
        {"object_id": "M1", "discipline": "mep", "member_type": "duct", "quantity": 5, "unit": "m"},
    ]
    after = [
        {"object_id": "W1", "discipline": "architecture", "member_type": "wall", "quantity": 24, "unit": "m2"},
        {"object_id": "S1", "discipline": "structural", "member_type": "steel", "quantity": 10, "unit": "m", "steel_weight_kg": 550},
        {"object_id": "D1", "discipline": "architecture", "member_type": "door", "quantity": 2, "unit": "عدد"},
    ]
    changes = compare_project_revisions(before, after, before_revision="R01", after_revision="R02")
    by_key = {r["revision_key"]: r for r in changes}
    assert by_key["W1"]["quantity_delta"] == 4
    assert by_key["S1"]["steel_delta"] == 50
    assert by_key["M1"]["change_type"] == "removed"
    assert by_key["D1"]["change_type"] == "added"
    assert by_key["W1"]["review_required"] is True


def test_concrete_and_rebar_impacts_are_explicit_not_guessed():
    changes = compare_project_revisions(
        [{"object_id": "C1", "quantity": 10, "concrete_volume_m3": 10, "rebar_weight_kg": 900}],
        [{"object_id": "C1", "quantity": 12, "concrete_volume_m3": 12.5, "rebar_weight_kg": 1020}],
    )
    row = changes[0]
    assert row["concrete_delta"] == pytest.approx(2.5)
    assert row["rebar_delta"] == pytest.approx(120)


def test_no_automatic_acceptance_or_quantity_mutation():
    before = [{"object_id": "A1", "quantity": 10}]
    after = [{"object_id": "A1", "quantity": 15}]
    changes = compare_project_revisions(before, after)
    original = dict(changes[0])
    reviewed, audit = apply_change_review(changes)
    assert reviewed[0]["review_status"] == "pending"
    assert reviewed[0]["quantity_after"] == original["quantity_after"]
    assert reviewed[0]["quantity_delta"] == original["quantity_delta"]
    assert audit[0]["decision"] == "pending"
    approved, _ = apply_change_review(changes, {"A1": True}, reviewer="engineer")
    assert approved[0]["review_status"] == "approved"


def test_rejected_revision_never_changes_the_underlying_quantity():
    changes = compare_project_revisions(
        [{"object_id": "A1", "quantity": 10}],
        [{"object_id": "A1", "quantity": 15}],
    )
    reviewed, _ = apply_change_review(changes, {"A1": False})
    assert reviewed[0]["review_status"] == "rejected"
    assert reviewed[0]["quantity_after"] == 15


def test_boq_revision_impact_tracks_quantity_and_cost():
    impact = boq_revision_impact(
        [{"item_code": "B1", "description": "Wall", "quantity": 10, "unit": "m2", "total": 1000}],
        [{"item_code": "B1", "description": "Wall", "quantity": 12, "unit": "m2", "total": 1200},
         {"item_code": "B2", "description": "Door", "quantity": 2, "unit": "عدد", "total": 300}],
    )
    assert impact["summary"]["quantity_delta"] == 4
    assert impact["summary"]["cost_delta"] == 500
    assert impact["finalizable_after_review"] is False


def test_revision_history_preserves_all_snapshots_deterministically():
    history = build_revision_history([
        {"revision": "R02", "created_at": "2026-10-02T02:00:00Z"},
        {"revision": "R01", "created_at": "2026-10-01T02:00:00Z"},
        {"revision": "R02", "created_at": "2026-10-02T01:00:00Z"},
    ])
    assert [x["created_at"] for x in history] == [
        "2026-10-01T02:00:00Z", "2026-10-02T01:00:00Z", "2026-10-02T02:00:00Z"
    ]
    assert len(history) == 3


def test_rtl_report_rows_are_stable_and_persian_labeled():
    rows = to_rtl_report_rows([
        {"revision_key": "C1", "change_type": "changed", "discipline": "structural",
         "description_after": "Column", "quantity_delta": 2, "rebar_delta": 40,
         "cost_delta": 1000, "review_status": "pending"}
    ])
    assert rows == [{
        "change_type": "تغییرکرده",
        "revision_key": "C1",
        "discipline": "structural",
        "description": "Column",
        "quantity_delta": 2.0,
        "material_delta": 40.0,
        "cost_delta": 1000.0,
        "review_status": "pending",
    }]
