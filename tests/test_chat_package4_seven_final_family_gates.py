"""Phase 1 / Chat package 4 / step 7: seven bounded generic AEC family gates.

These tests use synthetic EXPLICIT measurements and sourced component schedules.
No design quantity, waste, historic restoration approval, seismic engineering
suitability, excavation safety, facade design or price may be inferred.
Passing them establishes only generic contract/storage and negative controls.
"""
from copy import deepcopy

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system


# A reviewed quantity is entered, never calculated from an undocumented factor.
# "paving", "selective_demolition" and "stabilization" have no fixed unit
# semantics in the generic SPECS: only a source-specific measured unit is used.
FAMILIES = (
    ("facade_cladding", "building", (("panels", "عدد", "4"),)),
    ("external_works", "civil", (("paving", "m2", "24.5"),)),
    ("site_drains", "civil", (("pipes", "m", "17.5"),)),
    ("demolition", "building", (("selective_demolition", "m3", "12"),)),
    ("concrete_repair", "building", (("repair_mortar", "m3", "0.8"),)),
    ("seismic_retrofit", "building", (("anchorage", "عدد", "8"),)),
    ("historic_restoration", "building",
     (("documentation", "عدد", "2"), ("stabilization", "m2", "11"))),
)
WRONG_UNITS = (
    ("facade_cladding", "panels", "kg"),
    ("site_drains", "pipes", "m3"),
    ("concrete_repair", "repair_mortar", "kg"),
    ("seismic_retrofit", "anchorage", "m"),
)


def make_document(family):
    kind, domain, essentials = family
    assert set(SPECS[kind].essential) == {name for name, _, _ in essentials}
    data = empty_system(kind, "L1", "ZONE1")
    data["source"] = {
        "mode": "manual", "source_id": "SYNTHETIC-SITE-" + kind,
    }
    for name in SPECS[kind].components:
        data["components"][name] = {
            "status": "not_applicable",
            "reason": "Explicit synthetic exclusion; cannot be inferred as absent",
            "source_ref": "SYNTHETIC-BOUNDED-SCOPE",
            "approved_by": "SYNTHETIC-REVIEWER",
        }
    for name, unit, quantity in essentials:
        data["components"][name] = {
            "status": "confirmed",
            "approved_by": "SYNTHETIC-REVIEWER",
            "items": [{
                "line_id": "ITEM-" + name,
                "source_ref": "SYNTHETIC-FAMILY-DRAWING",
                "description": "Explicit measured synthetic " + name,
                "domain": domain,
                "item_code": "SYN-" + name,
                "mode": "measured", "quantity": quantity,
                "unit": unit,
                "formula": "Source-backed bounded input; no inferred area or count",
                "measurement_ref": "SYNTHETIC-TRACE-" + name,
            }],
        }
    return data


@pytest.mark.parametrize("family", FAMILIES)
def test_manually_entered_reviewed_quantities_match_documented_family(family):
    data = make_document(family)
    previous = deepcopy(data)
    out = preview_system(data, TakeoffEngine())
    assert out["ready"] and out["preview_only"] and not out["blockers"], out["blockers"]
    assert len(out["rows"]) == len(family[2])
    assert {row["component"] for row in out["rows"]} == set(SPECS[family[0]].essential)
    assert {row["domain"] for row in out["rows"]} == {family[1]}
    assert all(row["method"] == "measured" and row["measurement_ref"] for row in out["rows"])
    assert all(row["source_id"].startswith("aec:" + family[0] + ":") for row in out["rows"])
    assert len({row["source_id"] for row in out["rows"]}) == len(out["rows"])
    assert data == previous


@pytest.mark.parametrize("family", FAMILIES)
def test_missing_project_measurement_source_never_exposes_partial_rows(family):
    data = make_document(family)
    data["source"] = {}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["blockers"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_unreviewed_essential_group_discards_all_preview_quantities(family):
    data = make_document(family)
    data["components"][family[2][-1][0]] = {"status": "unreviewed"}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_required_group_cannot_be_marked_not_applicable(family):
    data = make_document(family)
    data["components"][family[2][0][0]] = {
        "status": "not_applicable",
        "reason": "Attempt to omit an essential item",
        "source_ref": "SYNTHETIC", "approved_by": "SYNTHETIC",
    }
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("ضروری" in m for m in out["blockers"])


@pytest.mark.parametrize("family", FAMILIES)
def test_missing_group_approval_never_defaults_to_approved(family):
    data = make_document(family)
    data["components"][family[2][0][0]]["approved_by"] = ""
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_wrong_discipline_cannot_convert_civil_to_building_or_reverse(family):
    data = make_document(family)
    item = data["components"][family[2][0][0]]["items"][0]
    item["domain"] = "civil" if family[1] == "building" else "mechanical"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_zero_quantity_is_not_valid_measured_work(family):
    data = make_document(family)
    data["components"][family[2][0][0]]["items"][0]["quantity"] = "0"
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_duplicate_measurement_line_is_not_added_to_total_twice(family):
    data = make_document(family)
    rows = data["components"][family[2][0][0]]["items"]
    rows.append(deepcopy(rows[0]))
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("تکراری" in m for m in out["blockers"])


@pytest.mark.parametrize("family", FAMILIES)
def test_independent_measurement_reference_is_mandatory(family):
    data = make_document(family)
    data["components"][family[2][0][0]]["items"][0].pop("measurement_ref")
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_unverified_arbitrary_formula_not_in_whitelist_cannot_run(family):
    data = make_document(family)
    item = data["components"][family[2][0][0]]["items"][0]
    item.update(mode="engine", item="invented_geometry_or_waste", params={})
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_sqlite_roundtrip_and_stale_cas_preserve_draft_and_boq(tmp_path, family):
    path = tmp_path / "db"
    data = make_document(family)
    original = deepcopy(data)
    app = StructuralProApp(path)
    try:
        app.create_project("پروژه آموزشی مصنوعی", "P")
        entry = app.save_aec_system_draft("P", data, expected_revision=0)
        assert entry["revision"] == 1 and entry["status"] == "draft"
        before = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", data, expected_revision=0)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    reopened = StructuralProApp(path)
    try:
        got = reopened.get_aec_system("P", family[0], "L1", "ZONE1")
        assert got["revision"] == 1 and got["status"] == "draft"
        assert got["data"] == original
        assert reopened.open_project("P")["boq"] == []
    finally:
        reopened.store.close()


@pytest.mark.parametrize("family", FAMILIES)
def test_incomplete_committed_takeoff_is_blocked_without_database_mutation(tmp_path, family):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("پروژه آموزشی مصنوعی", "P")
        data = make_document(family)
        data["components"][family[2][-1][0]] = {"status": "unreviewed"}
        entry = app.save_aec_system_draft("P", data, expected_revision=0)
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_aec_system("P", family[0], "L1", "ZONE1",
                                  expected_revision=entry["revision"])
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()


@pytest.mark.parametrize("kind,component,wrong_unit", WRONG_UNITS)
def test_physical_component_unit_is_not_interchangeable(kind, component, wrong_unit):
    family = next(x for x in FAMILIES if x[0] == kind)
    data = make_document(family)
    data["components"][component]["items"][0]["unit"] = wrong_unit
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


def test_facade_panel_schedule_has_documented_piece_ids_not_auto_panel_estimate():
    data = make_document(FAMILIES[0])
    item = data["components"]["panels"]["items"][0]
    for field in ("quantity", "unit", "formula", "measurement_ref"):
        item.pop(field, None)
    item.update(mode="detail", detail_type="piece_schedule", details={"entries": [
        {"id": "PN-01", "count": "2", "source_ref": "SYNTHETIC-PANEL-DETAIL",
         "approved_by": "SYNTHETIC-REVIEWER", "spec_ref": "SYNTHETIC-PANEL-SPEC"},
        {"id": "PN-02", "count": "2", "source_ref": "SYNTHETIC-PANEL-DETAIL",
         "approved_by": "SYNTHETIC-REVIEWER", "spec_ref": "SYNTHETIC-PANEL-SPEC"},
    ]})
    out = preview_system(data, TakeoffEngine())
    assert out["ready"], out["blockers"]
    assert len(out["rows"]) == 1
    assert out["rows"][0]["method"] == "detail"
    assert out["rows"][0]["unit"] == "عدد"
    assert out["rows"][0]["quantity"] == pytest.approx(4)


def test_duplicate_facade_panel_physical_id_must_fail_closed():
    data = make_document(FAMILIES[0])
    item = data["components"]["panels"]["items"][0]
    for field in ("quantity", "unit", "formula", "measurement_ref"):
        item.pop(field, None)
    panel = {
        "id": "PN-01", "count": "2",
        "source_ref": "SYNTHETIC-PANEL-DETAIL",
        "approved_by": "SYNTHETIC-REVIEWER",
        "spec_ref": "SYNTHETIC-PANEL-SPEC",
    }
    item.update(mode="detail", detail_type="piece_schedule",
                details={"entries": [panel, deepcopy(panel)]})
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("تکراری" in m for m in out["blockers"])


def test_historic_restoration_requires_documentation_and_stabilization_together():
    data = make_document(FAMILIES[-1])
    assert set(SPECS["historic_restoration"].essential) == {
        "documentation", "stabilization",
    }
    data["components"]["stabilization"] = {"status": "unreviewed"}
    out = preview_system(data, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


def test_one_source_identity_cannot_be_reused_between_two_site_families(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("پروژه آموزشی مصنوعی", "P")
        first, second = make_document(FAMILIES[1]), make_document(FAMILIES[2])
        second["source"]["source_id"] = first["source"]["source_id"]
        app.save_aec_system_draft("P", first, expected_revision=0)
        before = deepcopy(app.open_project("P"))
        with pytest.raises(ValueError):
            app.save_aec_system_draft("P", second, expected_revision=0)
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
