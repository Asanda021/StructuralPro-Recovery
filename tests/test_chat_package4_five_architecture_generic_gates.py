"""Phase 1, Chat package 4 step 2: bounded family-specific generic AEC gates.

Synthetic, manually documented data. Passing tests prove only generic contract,
SQLite and rejection behavior, never specialty layout, IFC/CAD or Windows.
"""
from copy import deepcopy
import pytest

from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system
from core.platform.application import StructuralProApp

# Actual SPECS essentials; no material rates, dimensions or quantities inferred.
CASES = (
    ("gypsum_partition", (("frames", "عدد", "5"), ("boards", "عدد", "8"))),
    ("cement_render", (("render_coat", "m2", "12.5"),)),
    ("door_window", (("frame", "عدد", "2"),)),
    ("upvc_aluminium_windows", (("profiles", "m", "8.25"), ("glazing", "m2", "6.1"))),
    ("glass_curtain_wall", (("mullions", "m", "12.25"), ("glazing", "m2", "6.1"))),
)
UNITS = (
    ("gypsum_partition", "boards", "m2"),
    ("cement_render", "render_coat", "kg"),
    ("upvc_aluminium_windows", "glazing", "عدد"),
    ("glass_curtain_wall", "glazing", "kg"),
)


def make_document(kind, rows):
    assert set(SPECS[kind].essential) == {component for component, _, _ in rows}
    data = empty_system(kind, "L1", "ARCH1")
    data["source"] = {"mode": "manual", "source_id": "SYNTHETIC-ARCH-" + kind}
    for name in SPECS[kind].components:
        data["components"][name] = {
            "status": "not_applicable",
            "source_ref": "Synthetic independent detail review",
            "approved_by": "Synthetic second reviewer",
            "reason": "Explicit synthetic exclusion; not an inference",
        }
    for name, unit, quantity in rows:
        data["components"][name] = {
            "status": "confirmed",
            "approved_by": "Synthetic second reviewer",
            "items": [{
                "line_id": "LINE-" + name, "source_ref": "Synthetic quantity drawing",
                "description": "Documented synthetic " + name,
                "domain": "building", "item_code": "SYN-" + name,
                "mode": "measured", "quantity": quantity,
                "unit": unit, "formula": "Independently supplied measured quantity",
                "measurement_ref": "SYNTHETIC-MEASURE-" + name,
            }],
        }
    return data


@pytest.mark.parametrize("kind,rows", CASES)
def test_one_real_generic_route_per_required_architecture_component(kind, rows):
    doc = make_document(kind, rows)
    original = deepcopy(doc)
    result = preview_system(doc, TakeoffEngine())
    assert result["ready"], result["blockers"]
    assert result["preview_only"] is True
    assert len(result["rows"]) == len(rows)
    assert {r["component"] for r in result["rows"]} == set(SPECS[kind].essential)
    assert all(r["method"] == "measured" and r["measurement_ref"] for r in result["rows"])
    assert all(r["source_id"].startswith("aec:" + kind + ":") for r in result["rows"])
    assert doc == original


@pytest.mark.parametrize("kind,rows", CASES)
def test_one_missing_required_group_hides_every_partial_row(kind, rows):
    doc = make_document(kind, rows)
    doc["components"][SPECS[kind].essential[-1]] = {"status": "unreviewed"}
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["blockers"]
    assert result["rows"] == []


@pytest.mark.parametrize("kind,rows", CASES)
def test_required_group_cannot_be_marked_not_applicable(kind, rows):
    doc = make_document(kind, rows)
    name = SPECS[kind].essential[0]
    doc["components"][name] = {
        "status": "not_applicable", "source_ref": "Synthetic",
        "approved_by": "Reviewer", "reason": "Attempted exclusion",
    }
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []
    assert any("ضروری" in error for error in result["blockers"])


@pytest.mark.parametrize("kind,rows", CASES)
def test_missing_component_approval_is_not_auto_approved(kind, rows):
    doc = make_document(kind, rows)
    doc["components"][rows[0][0]]["approved_by"] = ""
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []


@pytest.mark.parametrize("kind,rows", CASES)
def test_duplicate_measured_line_fails_closed(kind, rows):
    doc = make_document(kind, rows)
    items = doc["components"][rows[0][0]]["items"]
    items.append(deepcopy(items[0]))
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []
    assert any("تکراری" in error for error in result["blockers"])


@pytest.mark.parametrize("kind,rows", CASES)
def test_zero_is_not_interpreted_as_missing_or_as_measured_quantity(kind, rows):
    doc = make_document(kind, rows)
    doc["components"][rows[0][0]]["items"][0]["quantity"] = "0"
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []


@pytest.mark.parametrize("kind,rows", CASES)
def test_wrong_discipline_does_not_convert_architecture_into_electrical(kind, rows):
    doc = make_document(kind, rows)
    doc["components"][rows[0][0]]["items"][0]["domain"] = "electrical"
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []


@pytest.mark.parametrize("kind,component,invalid_unit", UNITS)
def test_physical_unit_mismatch_rejected(kind, component, invalid_unit):
    rows = next(rows for family, rows in CASES if family == kind)
    doc = make_document(kind, rows)
    doc["components"][component]["items"][0]["unit"] = invalid_unit
    result = preview_system(doc, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []


@pytest.mark.parametrize("kind,rows", CASES)
def test_incomplete_sqlite_draft_cannot_write_boq(tmp_path, kind, rows):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("پروژه آموزشی مصنوعی", "P")
        doc = make_document(kind, rows)
        doc["components"][SPECS[kind].essential[-1]] = {"status": "unreviewed"}
        record = app.save_aec_system_draft("P", doc, expected_revision=0)
        assert record["revision"] == 1 and record["status"] == "draft"
        before = deepcopy(app.open_project("P"))
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_aec_system("P", kind, "L1", "ARCH1", expected_revision=1)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()


@pytest.mark.parametrize("kind,rows", CASES)
def test_generic_sqlite_roundtrip_cas_without_financial_commit(tmp_path, kind, rows):
    path = tmp_path / "db"
    app = StructuralProApp(path)
    try:
        app.create_project("پروژه آموزشی مصنوعی", "P")
        doc = make_document(kind, rows)
        original = deepcopy(doc)
        record = app.save_aec_system_draft("P", doc, expected_revision=0)
        assert record["status"] == "draft" and record["revision"] == 1
        assert doc == original
        before = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", doc, expected_revision=0)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    reopened = StructuralProApp(path)
    try:
        got = reopened.get_aec_system("P", kind, "L1", "ARCH1")
        assert got["revision"] == 1 and got["status"] == "draft"
        assert got["data"] == original
        assert reopened.open_project("P")["boq"] == []
    finally:
        reopened.store.close()


def test_two_family_drafts_cannot_reuse_the_same_measurement_source(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("مصنوعی", "P")
        first = make_document(*CASES[0])
        second = make_document(*CASES[1])
        second["source"]["source_id"] = first["source"]["source_id"]
        app.save_aec_system_draft("P", first, expected_revision=0)
        before = deepcopy(app.open_project("P"))
        with pytest.raises(ValueError):
            app.save_aec_system_draft("P", second, expected_revision=0)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
