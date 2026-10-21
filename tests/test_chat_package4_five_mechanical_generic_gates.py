"""Phase 1 / Chat package 4, mechanical five-family safety and evidence routes.

Synthetic measurements are supplied explicitly. Passing these tests would prove
only generic AEC engine, draft/SQLite and fail-closed gates, NOT engineering design,
network layout, real MEP material schedules, Windows UI or Office acceptance.
"""
from copy import deepcopy

import pytest

from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system
from core.platform.application import StructuralProApp


# All names/essential groups are from the existing production SPECS.
# A duct surface is not a duct volume. Nothing here calculates pipe fittings,
# insulation, duct pressure loss, equipment selection or material wastage.
MECH = (
    ("plumbing", "pipes", "m", "11.25", "pipe", {"length": "5.625", "count": "2"}),
    ("sanitary_drainage", "pipes", "m", "9.5", "pipe", {"length": "4.75", "count": "2"}),
    ("hvac", "equipment", "عدد", "2", "equipment", {"count": "2"}),
    ("mechanical_ventilation", "ducts", "m2", "16.25", "duct_area",
     {"width": "0.4", "height": "0.25", "length": "12.5"}),
    ("plantroom", "equipment", "عدد", "3", "equipment", {"count": "3"}),
)
WRONG_UNITS = (
    ("plumbing", "kg"),
    ("sanitary_drainage", "عدد"),
    ("hvac", "m"),
    ("plantroom", "m3"),
)


def document(kind, essential, unit, quantity, route, inputs):
    assert tuple(SPECS[kind].essential) == (essential,)
    data = empty_system(kind, "L1", "MECH1")
    data["source"] = {
        "mode": "manual",
        "source_id": "SYNTHETIC-MECHANICAL-" + kind,
    }
    for name in SPECS[kind].components:
        data["components"][name] = {
            "status": "not_applicable",
            "reason": "Explicitly outside the synthetic measured scope",
            "source_ref": "SYNTHETIC-MEP-SCOPE",
            "approved_by": "SYNTHETIC-REVIEWER",
        }
    data["components"][essential] = {
        "status": "confirmed",
        "approved_by": "SYNTHETIC-REVIEWER",
        "items": [{
            "line_id": "ITEM1",
            "source_ref": "SYNTHETIC-MEP-DRAWING",
            "spec_ref": "SYNTHETIC-EQUIPMENT-AND-MATERIAL-SPEC",
            "description": "Synthetic documented " + essential,
            "domain": "mechanical",
            "item_code": "MEP-" + essential,
            "mode": "measured",
            "quantity": quantity,
            "unit": unit,
            "formula": "Direct measured input, no inferred fittings or waste",
            "measurement_ref": "SYNTHETIC-SURVEY-ITEM1",
        }],
    }
    return data


def engine_document(args):
    kind, essential, unit, quantity, route, inputs = args
    data = document(*args)
    item = data["components"][essential]["items"][0]
    item["mode"] = "engine"
    item["item"] = route
    item["params"] = deepcopy(inputs)
    for key in ("quantity", "unit", "formula", "measurement_ref"):
        item.pop(key, None)
    return data


@pytest.mark.parametrize("args", MECH)
def test_measured_material_or_equipment_has_explicit_provenance(args):
    kind, essential, unit, quantity, route, inputs = args
    data = document(*args)
    before = deepcopy(data)
    out = preview_system(data, TakeoffEngine())
    assert out["ready"] and not out["blockers"], out["blockers"]
    assert out["preview_only"] is True and len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["component"] == essential and row["unit"] == unit
    assert row["quantity"] == pytest.approx(float(quantity))
    assert row["domain"] == "mechanical"
    assert row["method"] == "measured" and row["measurement_ref"]
    assert row["source_id"].startswith("aec:" + kind + ":")
    assert data == before


@pytest.mark.parametrize("args", MECH)
def test_actual_existing_mechanical_engine_route_uses_supplied_dimensions(args):
    kind, essential, unit, quantity, route, inputs = args
    data = engine_document(args)
    prior = deepcopy(data)
    out = preview_system(data, TakeoffEngine())
    assert out["ready"], out["blockers"]
    assert len(out["rows"]) == 1
    row = out["rows"][0]
    independently_computed = TakeoffEngine().calculate("mechanical", route, **inputs)
    assert row["method"] == "engine"
    assert row["unit"] == unit == independently_computed.unit
    assert row["quantity"] == pytest.approx(float(quantity))
    assert row["quantity"] == pytest.approx(independently_computed.quantity)
    assert row["params"] == inputs
    assert data == prior


@pytest.mark.parametrize("args", MECH)
def test_missing_technical_spec_blocks_all_visible_quantities(args):
    data = document(*args)
    essential = args[1]
    data["components"][essential]["items"][0].pop("spec_ref")
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("مشخصات" in e for e in out["blockers"])


@pytest.mark.parametrize("args", MECH)
def test_mechanical_family_cannot_claim_electrical_domain(args):
    data = document(*args)
    data["components"][args[1]]["items"][0]["domain"] = "electrical"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("args", MECH)
def test_one_unreviewed_essential_component_rejects_partial_preview(args):
    data = document(*args)
    data["components"][args[1]] = {"status": "unreviewed"}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("args", MECH)
def test_required_family_component_cannot_be_declared_not_applicable(args):
    data = document(*args)
    data["components"][args[1]] = {
        "status": "not_applicable",
        "reason": "Attempted omission",
        "source_ref": "SYNTHETIC-REFERENCE",
        "approved_by": "SYNTHETIC-REVIEWER",
    }
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("ضروری" in message for message in out["blockers"])


@pytest.mark.parametrize("args", MECH)
def test_measured_component_without_approval_is_not_ready(args):
    data = document(*args)
    data["components"][args[1]]["approved_by"] = ""
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("args", MECH)
def test_duplicate_mechanical_line_id_cannot_produce_payable_rows(args):
    data = document(*args)
    items = data["components"][args[1]]["items"]
    items.append(deepcopy(items[0]))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("تکراری" in message for message in out["blockers"])


@pytest.mark.parametrize("args", MECH)
def test_zero_measured_quantity_is_not_an_implicit_placeholder(args):
    data = document(*args)
    data["components"][args[1]]["items"][0]["quantity"] = "0"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("kind,wrong_unit", WRONG_UNITS)
def test_physically_incompatible_pipe_or_equipment_unit_is_rejected(kind, wrong_unit):
    args = next(item for item in MECH if item[0] == kind)
    data = document(*args)
    data["components"][args[1]]["items"][0]["unit"] = wrong_unit
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("args", MECH)
def test_engine_missing_a_required_dimension_never_guesses(args):
    data = engine_document(args)
    item = data["components"][args[1]]["items"][0]
    item["params"].pop(next(iter(item["params"])))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("args", MECH)
def test_sqlite_reopen_and_stale_cas_do_not_touch_boq(tmp_path, args):
    kind = args[0]
    path = tmp_path / "db"
    app = StructuralProApp(path)
    doc = document(*args)
    original = deepcopy(doc)
    try:
        app.create_project("پروژه آموزشی مکانیک", "P")
        record = app.save_aec_system_draft("P", doc, expected_revision=0)
        assert record["revision"] == 1 and record["status"] == "draft"
        before = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", doc, expected_revision=0)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    reopened = StructuralProApp(path)
    try:
        saved = reopened.get_aec_system("P", kind, "L1", "MECH1")
        assert saved["revision"] == 1 and saved["status"] == "draft"
        assert saved["data"] == original
        assert reopened.open_project("P")["boq"] == []
    finally:
        reopened.store.close()


@pytest.mark.parametrize("args", MECH)
def test_incomplete_mechanical_draft_cannot_commit_to_boq(tmp_path, args):
    kind = args[0]
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("مصنوعی مکانیک", "P")
        doc = document(*args)
        doc["components"][args[1]] = {"status": "unreviewed"}
        record = app.save_aec_system_draft("P", doc, expected_revision=0)
        before = deepcopy(app.open_project("P"))
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_aec_system("P", kind, "L1", "MECH1", expected_revision=record["revision"])
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()


def test_two_mechanical_families_cannot_reuse_one_source_identity(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("مصنوعی", "P")
        first = document(*MECH[0])
        second = document(*MECH[1])
        second["source"]["source_id"] = first["source"]["source_id"]
        app.save_aec_system_draft("P", first, expected_revision=0)
        before = deepcopy(app.open_project("P"))
        with pytest.raises(ValueError):
            app.save_aec_system_draft("P", second, expected_revision=0)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
