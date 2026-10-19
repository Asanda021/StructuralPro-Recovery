"""Package 4 Chat: bounded safety gates for five generic roof families.

Passing these tests proves draft/preview/version safety only. It is NOT
engineering validation of specialist quantities or real drawing takeoff.
"""
from copy import deepcopy

import pytest

from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system
from core.platform.application import StructuralProApp

# One existing component per family, with a documented, deliberately partial input.
# Other essential components are left unreviewed to exercise the real fail-closed path.
ROOFS = (
    ("kromit_roof", "joists", "عدد"),
    ("composite_roof", "steel_members", "kg"),
    ("sandwich_roof", "panels", "عدد"),
    ("timber_roof", "joists", "عدد"),
    ("precast_roof", "precast_units", "عدد"),
)


def partial(kind, component, unit):
    data = empty_system(kind, "L1", "TEST1")
    data["components"][component] = {
        "status": "confirmed",
        "approved_by": "Synthetic Reviewer",
        "items": [{
            "line_id": "Q1", "source_ref": "Synthetic drawing detail",
            "description": "Measured synthetic component", "domain": "building",
            "item_code": "SYN-Q1", "mode": "measured",
            "quantity": "2", "unit": unit,
            "formula": "Explicit synthetic measurement",
            "measurement_ref": "Synthetic trace Q1",
        }],
    }
    return data


@pytest.mark.parametrize("kind,component,unit", ROOFS)
def test_incomplete_specialty_cannot_expose_partial_measured_rows(kind, component, unit):
    data = partial(kind, component, unit)
    before = deepcopy(data)
    out = preview_system(data, TakeoffEngine())
    assert out["ready"] is False
    assert out["blockers"]
    assert out["rows"] == []
    assert out["preview_only"] is True
    assert data == before


@pytest.mark.parametrize("kind,component,unit", ROOFS)
def test_missing_required_component_is_not_auto_assumed(kind, component, unit):
    data = empty_system(kind, "L1", "TEST1")
    required = SPECS[kind].essential[0]
    data["components"][required] = {
        "status": "not_applicable", "reason": "Synthetic, cannot omit",
        "source_ref": "Synthetic scope", "approved_by": "Reviewer",
    }
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("ضروری" in message for message in out["blockers"])


@pytest.mark.parametrize("kind,component,unit", ROOFS)
def test_sqlite_incomplete_roof_remains_draft_after_reopen(tmp_path, kind, component, unit):
    db = tmp_path / "storage"
    app = StructuralProApp(db)
    try:
        app.create_project("پروژه مصنوعی", "P")
        initial = app.new_aec_system(kind, "L1", "TEST1")
        saved = app.save_aec_system_draft("P", initial, expected_revision=0)
        assert saved["revision"] == 1 and saved["status"] == "draft"
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_aec_system("P", kind, "L1", "TEST1", expected_revision=1)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    reopened = StructuralProApp(db)
    try:
        record = reopened.get_aec_system("P", kind, "L1", "TEST1")
        assert record["status"] == "draft" and record["revision"] == 1
        assert reopened.open_project("P")["boq"] == []
    finally:
        reopened.store.close()


@pytest.mark.parametrize("kind,component,unit", ROOFS)
def test_stale_sqlite_revision_cannot_overwrite_record(tmp_path, kind, component, unit):
    app = StructuralProApp(tmp_path / "storage")
    try:
        app.create_project("پروژه مصنوعی", "P")
        initial = app.new_aec_system(kind, "L1", "TEST1")
        app.save_aec_system_draft("P", initial, expected_revision=0)
        before = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", initial, expected_revision=0)
        assert app.open_project("P") == before
    finally:
        app.store.close()
