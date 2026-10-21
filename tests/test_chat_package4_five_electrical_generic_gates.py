"""Phase 1, Chat package 4, step 4: bounded electrical AEC family tests.

Real existing electrical engine routes and synthetic user-supplied measurements.
A passing run is evidence only for reviewed generic AEC safety and storage.
It is not electrical engineering approval, CAD takeoff, Qt or Windows acceptance.
"""
from copy import deepcopy

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system


# Exact component names come from SPECS. Every essential group is supplied.
# No cable path, protective device, detector count or wiring allowance is inferred.
ELECTRICAL = (
    ("electrical_power", (("cables", "m", "9.5"),)),
    ("lighting", (("fixtures", "عدد", "3"),)),
    ("low_voltage", (("devices", "عدد", "5"),)),
    ("fire_alarm", (("detectors", "عدد", "4"), ("panels", "عدد", "2"))),
    ("data_network", (("cables", "m", "25"),)),
)
# A permitted engine route is used only with the corresponding allowed
# component and its complete, explicitly supplied input fields.
ENGINE = (
    ("electrical_power", "cables", "cable", {"length": "4.75", "count": "2"}, "m", 9.5),
    ("lighting", "fixtures", "light", {"count": "3"}, "عدد", 3),
    ("low_voltage", "cables", "cable", {"length": "7.5", "count": "2"}, "m", 15),
    ("fire_alarm", "panels", "panel", {"count": "2"}, "عدد", 2),
    ("data_network", "cables", "cable", {"length": "12.5", "count": "2"}, "m", 25),
)
WRONG_UNIT = (
    ("electrical_power", "cables", "عدد"),
    ("lighting", "fixtures", "m"),
    ("low_voltage", "devices", "kg"),
    ("fire_alarm", "detectors", "m"),
    ("data_network", "cables", "kg"),
)


def document(kind, essentials):
    assert set(SPECS[kind].essential) == {name for name, _, _ in essentials}
    data = empty_system(kind, "L1", "ELEC1")
    data["source"] = {"mode": "manual", "source_id": "SYNTHETIC-ELECTRICAL-" + kind}
    for name in SPECS[kind].components:
        data["components"][name] = {
            "status": "not_applicable",
            "source_ref": "SYNTHETIC-ELECTRICAL-SCOPE",
            "approved_by": "SYNTHETIC-REVIEWER",
            "reason": "Independently excluded in synthetic scoped fixture",
        }
    for name, unit, value in essentials:
        data["components"][name] = {
            "status": "confirmed",
            "approved_by": "SYNTHETIC-REVIEWER",
            "items": [{
                "line_id": "MEASURE-" + name,
                "source_ref": "SYNTHETIC-ELECTRICAL-DRAWING",
                "spec_ref": "SYNTHETIC-ELECTRICAL-TECHNICAL-SPEC",
                "description": "Synthetic measured " + name,
                "domain": "electrical",
                "item_code": "ELEC-" + name,
                "mode": "measured",
                "quantity": value,
                "unit": unit,
                "formula": "Independent synthetic measurement, no inferred multiplier",
                "measurement_ref": "SYNTHETIC-QUANTITY-TRACE-" + name,
            }],
        }
    return data


def engine_document(case):
    kind, component, route, params, unit, quantity = case
    essentials = next(e for family, e in ELECTRICAL if family == kind)
    data = document(kind, essentials)
    if data["components"][component]["status"] == "not_applicable":
        data["components"][component] = {
            "status": "confirmed", "approved_by": "SYNTHETIC-REVIEWER",
            "items": [{
                "line_id": "ENGINE-" + component,
                "source_ref": "SYNTHETIC-ELECTRICAL-DRAWING",
                "spec_ref": "SYNTHETIC-ELECTRICAL-TECHNICAL-SPEC",
                "description": "Documented route " + route,
                "domain": "electrical", "item_code": "ELEC-" + component,
                "mode": "engine", "item": route, "params": deepcopy(params),
            }],
        }
    else:
        row = data["components"][component]["items"][0]
        for field in ("quantity", "unit", "formula", "measurement_ref"):
            row.pop(field, None)
        row.update(mode="engine", item=route, params=deepcopy(params))
    return data


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_manual_electrical_essential_components_retain_exact_user_scope(kind, essentials):
    data = document(kind, essentials)
    snapshot = deepcopy(data)
    result = preview_system(data, TakeoffEngine())
    assert result["ready"] and result["preview_only"] and not result["blockers"]
    assert len(result["rows"]) == len(essentials)
    assert {r["component"] for r in result["rows"]} == set(SPECS[kind].essential)
    assert all(r["method"] == "measured" and r["measurement_ref"] for r in result["rows"])
    assert all(r["domain"] == "electrical" and r["source_id"].startswith("aec:" + kind + ":")
               for r in result["rows"])
    assert data == snapshot


@pytest.mark.parametrize("case", ENGINE)
def test_real_electrical_engine_route_matches_documented_input(case):
    kind, component, route, params, unit, quantity = case
    data = engine_document(case)
    snapshot = deepcopy(data)
    result = preview_system(data, TakeoffEngine())
    assert result["ready"], result["blockers"]
    actual = next(r for r in result["rows"] if r["component"] == component)
    independent = TakeoffEngine().calculate("electrical", route, **params)
    assert actual["method"] == "engine"
    assert actual["unit"] == unit == independent.unit
    assert actual["quantity"] == pytest.approx(quantity)
    assert actual["quantity"] == pytest.approx(independent.quantity)
    assert actual["params"] == params
    assert data == snapshot


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_missing_electrical_technical_spec_hides_all_rows(kind, essentials):
    data = document(kind, essentials)
    data["components"][essentials[0][0]]["items"][0].pop("spec_ref")
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("مشخصات" in error for error in out["blockers"])


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_electrical_family_cannot_record_mechanical_line(kind, essentials):
    data = document(kind, essentials)
    data["components"][essentials[0][0]]["items"][0]["domain"] = "mechanical"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_missing_required_electrical_group_never_shows_partial_quantities(kind, essentials):
    data = document(kind, essentials)
    data["components"][essentials[-1][0]] = {"status": "unreviewed"}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["blockers"] and out["rows"] == []


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_required_electrical_group_cannot_be_excluded_as_optional(kind, essentials):
    data = document(kind, essentials)
    data["components"][essentials[0][0]] = {
        "status": "not_applicable",
        "reason": "Attempted removal", "source_ref": "SYNTHETIC-SCOPE",
        "approved_by": "SYNTHETIC-REVIEWER",
    }
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("ضروری" in error for error in out["blockers"])


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_missing_electrical_approver_never_becomes_approved_by_default(kind, essentials):
    data = document(kind, essentials)
    data["components"][essentials[0][0]]["approved_by"] = ""
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_duplicate_line_in_a_component_is_not_double_counted(kind, essentials):
    data = document(kind, essentials)
    items = data["components"][essentials[0][0]]["items"]
    items.append(deepcopy(items[0]))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("تکراری" in error for error in out["blockers"])


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_zero_electrical_quantity_is_not_accepted_as_real_measurement(kind, essentials):
    data = document(kind, essentials)
    data["components"][essentials[0][0]]["items"][0]["quantity"] = "0"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("kind,component,invalid_unit", WRONG_UNIT)
def test_electrical_physical_unit_mismatch_rejected(kind, component, invalid_unit):
    essentials = next(e for family, e in ELECTRICAL if family == kind)
    data = document(kind, essentials)
    data["components"][component]["items"][0]["unit"] = invalid_unit
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("case", ENGINE)
def test_engine_missing_mandatory_input_never_defaults_unknown_count_or_length(case):
    data = engine_document(case)
    item = data["components"][case[1]]["items"][0]
    item["params"].pop(next(iter(item["params"])))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_sqlite_reopen_keeps_electrical_draft_and_cas_without_boq(tmp_path, kind, essentials):
    path = tmp_path / "db"
    app = StructuralProApp(path)
    data = document(kind, essentials)
    before_draft = deepcopy(data)
    try:
        app.create_project("برق مصنوعی", "P")
        saved = app.save_aec_system_draft("P", data, expected_revision=0)
        assert saved["revision"] == 1 and saved["status"] == "draft"
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", data, expected_revision=0)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    reopen = StructuralProApp(path)
    try:
        saved = reopen.get_aec_system("P", kind, "L1", "ELEC1")
        assert saved["revision"] == 1 and saved["status"] == "draft"
        assert saved["data"] == before_draft
        assert reopen.open_project("P")["boq"] == []
    finally:
        reopen.store.close()


@pytest.mark.parametrize("kind,essentials", ELECTRICAL)
def test_incomplete_electrical_draft_fails_financial_commit_without_mutation(tmp_path, kind, essentials):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("برق مصنوعی", "P")
        data = document(kind, essentials)
        data["components"][essentials[-1][0]] = {"status": "unreviewed"}
        saved = app.save_aec_system_draft("P", data, expected_revision=0)
        prior = deepcopy(app.open_project("P"))
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_aec_system("P", kind, "L1", "ELEC1", expected_revision=saved["revision"])
        assert app.open_project("P") == prior
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()


def test_duplicate_source_across_two_electrical_families_is_rejected(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("مصنوعی", "P")
        first = document(*ELECTRICAL[0])
        second = document(*ELECTRICAL[1])
        second["source"]["source_id"] = first["source"]["source_id"]
        app.save_aec_system_draft("P", first, expected_revision=0)
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises(ValueError):
            app.save_aec_system_draft("P", second, expected_revision=0)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
