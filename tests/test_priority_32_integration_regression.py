"""Priority 32 — integration and regression coverage."""
from __future__ import annotations

import pytest

from core.platform.application import StructuralProApp


def _app(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Integration", "P32")
    return app


def test_recalculate_is_idempotent_and_persists(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff(
        "P32", "building", "slab_volume",
        length=5, width=4, thickness=0.2, price_code="A-1"
    )
    first = app.recalculate_estimate("P32")
    second = app.recalculate_estimate("P32")
    assert first["boq"] == second["boq"]
    assert first["cost"] == second["cost"]

    app.store.close()
    reopened = StructuralProApp(tmp_path / "data")
    project = reopened.open_project("P32")
    assert project is not None
    assert len(project["takeoffs"]) == 1


def test_recovery_round_trip_preserves_estimate_inputs(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff(
        "P32", "building", "slab_volume",
        length=3, width=4, thickness=0.2, price_code="A-1"
    )
    before = app.recalculate_estimate("P32")
    backup = tmp_path / "p32.json"
    app.export_project_backup("P32", backup)
    imported = app.import_project_backup(backup)
    assert imported["id"] == "P32"
    after = app.recalculate_estimate("P32")
    assert before["boq"] == after["boq"]
    assert before["cost"] == after["cost"]


def test_ai_review_does_not_change_estimate_or_takeoff_state(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff(
        "P32", "building", "slab_volume",
        length=2, width=3, thickness=0.2
    )
    estimate_before = app.recalculate_estimate("P32")
    before = app.open_project("P32")
    app.ai_assistant_respond("P32", "متره و برآورد پروژه را بررسی کن و ثبت کن")
    after = app.open_project("P32")
    estimate_after = app.recalculate_estimate("P32")
    assert before == after
    assert estimate_before["boq"] == estimate_after["boq"]
    assert estimate_before["cost"] == estimate_after["cost"]


def test_performance_snapshot_matches_project_collection_sizes(tmp_path):
    app = _app(tmp_path)
    for i in range(5):
        app.add_takeoff(
            "P32", "building", "slab_volume",
            length=2 + i, width=3, thickness=0.2, source_id=f"S{i}"
        )
    snap = app.project_performance_snapshot("P32")
    assert snap["project_id"] == "P32"
    assert snap["collection_counts"]["takeoffs"] == 5
    assert snap["total_collection_rows"] >= 5


def test_report_and_recalculation_share_same_takeoff_count(tmp_path):
    app = _app(tmp_path)
    for i in range(3):
        app.add_takeoff(
            "P32", "building", "slab_volume",
            length=2, width=2, thickness=0.2, source_id=f"R{i}"
        )
    estimate = app.recalculate_estimate("P32")
    activity = app.project_activity_summary("P32")
    assert estimate["boq"]
    assert activity["takeoffs"] == 3
    assert activity["boq_items"] == len(estimate["boq"])


def test_invalid_project_operations_fail_without_partial_creation(tmp_path):
    app = _app(tmp_path)
    with pytest.raises(ValueError):
        app.add_takeoff(
            "P32", "building", "slab_volume",
            length=-1, width=2, thickness=0.2
        )
    project = app.open_project("P32")
    assert project is not None
    assert project["takeoffs"] == []

# Regression suite intentionally remains offline and deterministic.
