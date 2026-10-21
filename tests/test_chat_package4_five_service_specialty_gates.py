"""Bounded family-specific generic MEP gates, not Windows/engineering acceptance."""
from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system

FAMILIES = (
    ("security_systems", "electrical", (("controllers", "عدد", "2"),)),
    ("emergency_power", "electrical", (("panels", "عدد", "2"),)),
    ("elevator", "electrical", (("car", "عدد", "1"), ("machine", "عدد", "1"))),
    ("natural_gas", "mechanical", (("pipes", "m", "15"),)),
    ("fire_protection", "mechanical", (("pipes", "m", "19"),)),
)
ENGINE = (
    ("security_systems", "cables", "electrical", "cable", {"length": "6.75", "count": "2"}, "m", 13.5),
    ("emergency_power", "panels", "electrical", "panel", {"count": "2"}, "عدد", 2),
    ("elevator", "cables", "electrical", "cable", {"length": "4", "count": "2"}, "m", 8),
    ("natural_gas", "pipes", "mechanical", "pipe", {"length": "7.5", "count": "2"}, "m", 15),
    ("fire_protection", "pipes", "mechanical", "pipe", {"length": "9.5", "count": "2"}, "m", 19),
)
WRONG_BINDING = (
    ("security_systems", "controllers", "electrical", "panel", {"count": "2"}),
    ("emergency_power", "panels", "electrical", "light", {"count": "2"}),
    ("elevator", "car", "electrical", "panel", {"count": "1"}),
    ("natural_gas", "pipes", "mechanical", "equipment", {"count": "1"}),
    ("fire_protection", "pipes", "mechanical", "equipment", {"count": "1"}),
)
WRONG_UNIT = (
    ("security_systems", "controllers", "m"),
    ("emergency_power", "panels", "m"),
    ("elevator", "car", "kg"),
    ("natural_gas", "pipes", "عدد"),
    ("fire_protection", "pipes", "kg"),
)

def case_for(kind):
    return next(x for x in FAMILIES if x[0] == kind)

def document(case):
    kind, domain, essential = case
    assert set(SPECS[kind].essential) == {name for name, _, _ in essential}
    data = empty_system(kind, "L1", "TEST")
    data["source"] = {"mode": "manual", "source_id": "SYNTHETIC-" + kind}
    for name in SPECS[kind].components:
        data["components"][name] = {
            "status": "not_applicable", "reason": "Explicitly out of scope",
            "source_ref": "SYNTHETIC-SCOPE", "approved_by": "SYNTHETIC-REVIEW",
        }
    for name, unit, quantity in essential:
        data["components"][name] = {
            "status": "confirmed", "approved_by": "SYNTHETIC-REVIEW",
            "items": [{
                "line_id": "LINE-" + name, "source_ref": "SYNTHETIC-DRAWING",
                "spec_ref": "SYNTHETIC-TECHNICAL-SPEC",
                "description": "Documented " + name, "domain": domain,
                "item_code": "SYN-" + name, "mode": "measured",
                "quantity": quantity, "unit": unit,
                "formula": "Directly entered synthetic quantity",
                "measurement_ref": "SYNTHETIC-TRACE-" + name,
            }],
        }
    return data

def with_engine(entry):
    kind, name, domain, route, params, unit, quantity = entry
    data = document(case_for(kind))
    group = data["components"][name]
    if group["status"] == "not_applicable":
        group = {"status": "confirmed", "approved_by": "SYNTHETIC-REVIEW",
                 "items": [{
                     "line_id": "ENGINE-" + name,
                     "source_ref": "SYNTHETIC-DRAWING",
                     "spec_ref": "SYNTHETIC-TECHNICAL-SPEC",
                     "description": "Documented engine " + name, "domain": domain,
                     "item_code": "ENGINE-" + name, "mode": "engine",
                     "item": route, "params": deepcopy(params),
                 }]}
        data["components"][name] = group
    else:
        row = group["items"][0]
        for field in ("quantity", "unit", "formula", "measurement_ref"):
            row.pop(field, None)
        row.update(mode="engine", item=route, params=deepcopy(params))
    return data

@pytest.mark.parametrize("case", FAMILIES)
def test_positive_manual_reviewed_components(case):
    data = document(case); old = deepcopy(data)
    out = preview_system(data, TakeoffEngine())
    assert out["ready"] and out["preview_only"] and not out["blockers"]
    assert len(out["rows"]) == len(case[2])
    assert {row["component"] for row in out["rows"]} == set(SPECS[case[0]].essential)
    assert len({row["source_id"] for row in out["rows"]}) == len(out["rows"])
    assert all(row["method"] == "measured" and row["measurement_ref"] for row in out["rows"])
    assert data == old

@pytest.mark.parametrize("entry", ENGINE)
def test_positive_existing_mep_engine_routes(entry):
    data = with_engine(entry); old = deepcopy(data)
    out = preview_system(data, TakeoffEngine())
    assert out["ready"], out["blockers"]
    rows = [r for r in out["rows"] if r["component"] == entry[1]]
    assert len(rows) == 1 and rows[0]["method"] == "engine"
    independently = TakeoffEngine().calculate(entry[2], entry[3], **entry[4])
    assert rows[0]["unit"] == entry[5] == independently.unit
    assert rows[0]["quantity"] == pytest.approx(entry[6])
    assert rows[0]["quantity"] == pytest.approx(independently.quantity)
    assert rows[0]["params"] == entry[4] and data == old

@pytest.mark.parametrize("entry", WRONG_BINDING)
def test_same_unit_cannot_launder_wrong_component_route(entry):
    kind, component, domain, route, params = entry
    data = document(case_for(kind))
    item = data["components"][component]["items"][0]
    for field in ("quantity", "unit", "formula", "measurement_ref"):
        item.pop(field, None)
    item.update(mode="engine", item=route, params=deepcopy(params))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("نوع مصالح و عضو" in m for m in out["blockers"])

@pytest.mark.parametrize("case", FAMILIES)
def test_missing_technical_spec_blocks_every_quantity(case):
    data = document(case)
    data["components"][case[2][0][0]]["items"][0].pop("spec_ref")
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("case", FAMILIES)
def test_cross_discipline_row_is_not_accepted(case):
    data = document(case)
    row = data["components"][case[2][0][0]]["items"][0]
    row["domain"] = "mechanical" if case[1] == "electrical" else "electrical"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("case", FAMILIES)
def test_unreviewed_essential_blocks_all_rows(case):
    data = document(case)
    data["components"][case[2][-1][0]] = {"status": "unreviewed"}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("case", FAMILIES)
def test_not_applicable_is_forbidden_for_essential(case):
    data = document(case)
    data["components"][case[2][0][0]] = {
        "status": "not_applicable", "source_ref": "SYN", "approved_by": "SYN",
        "reason": "Attempted omission",
    }
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("ضروری" in msg for msg in out["blockers"])

@pytest.mark.parametrize("case", FAMILIES)
def test_zero_quantity_fails_closed(case):
    data = document(case)
    data["components"][case[2][0][0]]["items"][0]["quantity"] = "0"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("entry", WRONG_UNIT)
def test_incompatible_physical_unit_fails_closed(entry):
    kind, component, wrong = entry
    data = document(case_for(kind))
    data["components"][component]["items"][0]["unit"] = wrong
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("case", FAMILIES)
def test_duplicate_line_id_does_not_double_count(case):
    data = document(case)
    items = data["components"][case[2][0][0]]["items"]
    items.append(deepcopy(items[0]))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("case", FAMILIES)
def test_missing_source_provenance_hides_partial_rows(case):
    data = document(case); data["source"] = {}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("entry", ENGINE)
def test_missing_engine_input_fails_closed(entry):
    data = with_engine(entry)
    params = data["components"][entry[1]]["items"][0]["params"]
    params.pop(next(iter(params)))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []

@pytest.mark.parametrize("case", FAMILIES)
def test_sqlite_reopen_cas_and_draft_cannot_mutate_boq(tmp_path, case):
    path = tmp_path / "db"; app = StructuralProApp(path)
    data = document(case); old = deepcopy(data)
    try:
        app.create_project("پروژه مصنوعی", "P")
        entry = app.save_aec_system_draft("P", data, expected_revision=0)
        assert entry["revision"] == 1 and entry["status"] == "draft"
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", data, expected_revision=0)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    app2 = StructuralProApp(path)
    try:
        entry = app2.get_aec_system("P", case[0], "L1", "TEST")
        assert entry["revision"] == 1 and entry["status"] == "draft"
        assert entry["data"] == old
        assert app2.open_project("P")["boq"] == []
    finally:
        app2.store.close()

@pytest.mark.parametrize("case", FAMILIES)
def test_incomplete_draft_cannot_commit_boq(tmp_path, case):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("پروژه مصنوعی", "P")
        data = document(case)
        data["components"][case[2][-1][0]] = {"status": "unreviewed"}
        entry = app.save_aec_system_draft("P", data, expected_revision=0)
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_aec_system("P", case[0], "L1", "TEST",
                                  expected_revision=entry["revision"])
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()

def test_duplicate_source_between_separate_families_rejected(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("پروژه مصنوعی", "P")
        first, second = document(FAMILIES[0]), document(FAMILIES[1])
        second["source"]["source_id"] = first["source"]["source_id"]
        app.save_aec_system_draft("P", first, expected_revision=0)
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises(ValueError):
            app.save_aec_system_draft("P", second, expected_revision=0)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
