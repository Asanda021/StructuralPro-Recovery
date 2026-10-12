"""Priority 33 — edge cases and failure-mode coverage."""
from __future__ import annotations

import pytest

from core.platform.application import StructuralProApp


def _app(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Edge Cases", "P33")
    return app


def test_invalid_dimensions_fail_without_mutation(tmp_path):
    app = _app(tmp_path)
    for params in (
        {"length": -1, "width": 2, "thickness": 0.2},
        {"length": 2, "width": -1, "thickness": 0.2},
        {"length": 2, "width": 2, "thickness": -0.2},
    ):
        with pytest.raises(ValueError):
            app.add_takeoff("P33", "building", "slab_volume", **params)
    assert app.open_project("P33")["takeoffs"] == []


def test_duplicate_source_is_fail_closed(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff("P33", "building", "slab_volume",
                    length=2, width=2, thickness=0.2, source_id="DRAW-1")
    with pytest.raises(ValueError):
        app.add_takeoff("P33", "building", "slab_volume",
                        length=3, width=3, thickness=0.2, source_id="DRAW-1")
    assert len(app.open_project("P33")["takeoffs"]) == 1


def test_invalid_estimate_factor_does_not_persist(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff("P33", "building", "slab_volume",
                    length=2, width=2, thickness=0.2)
    before = app.open_project("P33")
    with pytest.raises((ValueError, TypeError)):
        app.recalculate_estimate("P33", factors={"bad": "not-a-number"})
    after = app.open_project("P33")
    assert after == before


def test_pagination_rejects_invalid_boundaries(tmp_path):
    app = _app(tmp_path)
    with pytest.raises(ValueError):
        app.project_collection_page("P33", "takeoffs", page=0)
    with pytest.raises(ValueError):
        app.project_collection_page("P33", "takeoffs", page_size=0)
    with pytest.raises(ValueError):
        app.project_collection_page("P33", "unsupported", page=1)


def test_missing_project_operations_are_non_mutating(tmp_path):
    app = _app(tmp_path)
    with pytest.raises(KeyError):
        app.recalculate_estimate("MISSING")
    with pytest.raises(KeyError):
        app.project_performance_snapshot("MISSING")
    assert app.open_project("P33") is not None


def test_corrupt_recovery_payload_is_rejected(tmp_path):
    app = _app(tmp_path)
    path = tmp_path / "bad.json"
    path.write_text('{"id":"P33","name":"bad","takeoffs":"not-a-list"}', encoding="utf-8")
    from core.recovery.recovery import RecoveryError
    with pytest.raises(RecoveryError):
        app.import_project_backup(path)


def test_ai_confirmation_gate_does_not_mutate_state(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff("P33", "building", "slab_volume",
                    length=2, width=2, thickness=0.2)
    app.recalculate_estimate("P33")
    before = app.open_project("P33")
    response = app.ai_assistant_respond("P33", "متره را اجرا کن و ثبت کن")
    after = app.open_project("P33")
    assert before == after
    assert response["requires_confirmation"] is True
