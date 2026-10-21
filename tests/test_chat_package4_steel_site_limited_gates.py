"""Chat Package 4 step 6: bounded structural/site AEC evidence, no full acceptance.

Stair_metal is an inventory-only family without an identified reviewed AEC
contract. The tests must NOT equate concrete stairs or generic metalwork
with independently accepted steel stairs.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system


# Real family IDs and essential component IDs; every number here is supplied
# by a synthetic document, never inferred from dimensions or the family name.
CASES = (
    ("handrails_metalwork", "profiles", "building", "kg", 27),
    ("external_earthwork", "excavation", "civil", "m3", 12),
    ("blinding_concrete", "blinding_concrete", "advanced", "m3", .6),
    ("retaining_structures", "soldier_piles", "civil", "عدد", 2),
)


def document(case):
    kind, component, domain, unit, amount = case
    assert tuple(SPECS[kind].essential) == (component,)
    data = empty_system(kind, "L1", "COMP1")
    data["source"] = {
        "mode": "manual", "source_id": "SYNTHETIC-PHASE1-" + kind,
    }
    for name in SPECS[kind].components:
        data["components"][name] = {
            "status": "not_applicable", "approved_by": "SYNTHETIC-REVIEWER",
            "source_ref": "SYNTHETIC-COMPONENT-SCOPE",
            "reason": "Explicitly outside the bounded synthetic scope",
        }
    item = {
        "line_id": "LINE-" + component,
        "source_ref": "SYNTHETIC-DRAWING-REFERENCE",
        "description": "Synthetic documented " + component,
        "domain": domain, "item_code": "SYN-" + component,
    }
    if kind == "handrails_metalwork":
        item.update(
            mode="detail", detail_type="steel_profile_schedule",
            details={"entries": [{
                "id": "PROFILE-01", "source_ref": "SYNTHETIC-PROFILE-DETAIL",
                "approved_by": "SYNTHETIC-REVIEWER",
                "count": 2, "length_m": "3", "unit_weight_kg_m": "4.5",
                "unit_weight_source": "SYNTHETIC-PROFILE-CATALOGUE",
            }]},
        )
    elif kind == "blinding_concrete":
        item.update(
            mode="engine", item="footing_concrete",
            params={"length": "3", "width": "2", "thickness": ".1", "count": "1"},
        )
    else:
        item.update(
            mode="measured", quantity=str(amount), unit=unit,
            formula="Direct source-backed synthetic measured quantity",
            measurement_ref="SYNTHETIC-MEASUREMENT-" + component,
        )
    data["components"][component] = {
        "status": "confirmed", "approved_by": "SYNTHETIC-REVIEWER",
        "items": [item],
    }
    return data


@pytest.mark.parametrize("case", CASES)
def test_reviewed_source_bounded_positive_route_not_invented(case):
    doc = document(case); unchanged = deepcopy(doc)
    out = preview_system(doc, TakeoffEngine())
    assert out["ready"], out["blockers"]
    assert out["preview_only"] is True and len(out["rows"]) == 1
    row = out["rows"][0]
    assert row["component"] == case[1] and row["domain"] == case[2]
    assert row["unit"] == case[3]
    assert row["quantity"] == pytest.approx(case[4])
    assert row["source_id"].startswith("aec:" + case[0] + ":")
    assert doc == unchanged


@pytest.mark.parametrize("case", CASES)
def test_missing_registered_source_blocks_every_row(case):
    doc = document(case); doc["source"] = {}
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["blockers"] and out["rows"] == []


@pytest.mark.parametrize("case", CASES)
def test_unreviewed_essential_blocks_partial_preview(case):
    doc = document(case)
    doc["components"][case[1]] = {"status": "unreviewed"}
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("case", CASES)
def test_essential_cannot_be_excluded_with_not_applicable(case):
    doc = document(case)
    doc["components"][case[1]] = {
        "status": "not_applicable", "reason": "Attempted skip",
        "source_ref": "SYNTHETIC", "approved_by": "SYNTHETIC",
    }
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("ضروری" in msg for msg in out["blockers"])


@pytest.mark.parametrize("case", CASES)
def test_wrong_discipline_cannot_launder_quantity(case):
    doc = document(case)
    row = doc["components"][case[1]]["items"][0]
    row["domain"] = "civil" if case[2] != "civil" else "electrical"
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("case", CASES)
def test_approver_not_defaulted(case):
    doc = document(case); doc["components"][case[1]]["approved_by"] = ""
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("case", CASES)
def test_duplicate_line_in_one_component_does_not_count_twice(case):
    doc = document(case)
    lines = doc["components"][case[1]]["items"]
    lines.append(deepcopy(lines[0]))
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("case", CASES)
def test_zero_explicit_quantity_or_dimension_fails_closed(case):
    doc = document(case); item = doc["components"][case[1]]["items"][0]
    if case[0] == "handrails_metalwork":
        item["details"]["entries"][0]["count"] = 0
    elif case[0] == "blinding_concrete":
        item["params"]["thickness"] = "0"
    else:
        item["quantity"] = "0"
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


@pytest.mark.parametrize("case", CASES)
def test_missing_independent_quantity_evidence_rejected(case):
    doc = document(case); item = doc["components"][case[1]]["items"][0]
    if case[0] == "handrails_metalwork":
        item["details"]["entries"][0].pop("unit_weight_source")
    elif case[0] == "blinding_concrete":
        item["params"].pop("count")
    else:
        item.pop("measurement_ref")
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


def test_repeated_physical_profile_in_schedule_is_rejected():
    case = CASES[0]; doc = document(case)
    entries = doc["components"][case[1]]["items"][0]["details"]["entries"]
    entries.append(deepcopy(entries[0]))
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []
    assert any("تکراری" in msg for msg in out["blockers"])


@pytest.mark.parametrize("case,wrong_unit", (
    (CASES[1], "kg"),
    (CASES[2], "kg"),
))
def test_excavation_and_blinding_concrete_reject_incompatible_unit(case, wrong_unit):
    doc = document(case); item = doc["components"][case[1]]["items"][0]
    item.update(mode="measured", quantity="12", unit=wrong_unit,
                formula="SYNTHETIC-QUANTITY", measurement_ref="SYNTHETIC-TRACE")
    item.pop("item", None); item.pop("params", None)
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


def test_unreviewed_civil_engine_route_does_not_claim_approved_aec_formula():
    case = CASES[1]; doc = document(case)
    item = doc["components"][case[1]]["items"][0]
    item.update(mode="engine", item="excavation",
                params={"length": "3", "width": "2", "depth": "2"})
    out = preview_system(doc, TakeoffEngine())
    assert not out["ready"] and out["rows"] == []


def test_stair_metal_catalog_entry_is_unmapped_not_concrete_stair_contract():
    root = Path(__file__).resolve().parents[1]
    ledger = json.loads((root / "docs/aec_priority_1_9_master_inventory_20261013.json").read_text(encoding="utf-8"))
    entry = next(x for x in ledger["items"] if x["code"] == "stair_metal")
    assert entry["coverage_level"] == "requires_dedicated_acceptance"
    assert entry["route_file"] is None and entry["tests_verified"] is False
    assert "stair_metal" not in SPECS
    assert "waist_concrete" in SPECS["stair"].components
    with pytest.raises(KeyError):
        empty_system("stair_metal", "L1", "STAIR-STEEL")


def test_stair_metal_not_silently_routed_to_generic_aec_preview():
    with pytest.raises(ValueError):
        preview_system({"kind": "stair_metal", "floor_id": "L1",
                        "system_id": "STAIR-STEEL"}, TakeoffEngine())


@pytest.mark.parametrize("case", CASES)
def test_sqlite_persists_draft_and_stale_cas_cannot_touch_boq(tmp_path, case):
    db = tmp_path / "db"
    app = StructuralProApp(db)
    data = document(case); original = deepcopy(data)
    try:
        app.create_project("پروژه مصنوعی", "P")
        saved = app.save_aec_system_draft("P", data, expected_revision=0)
        assert saved["revision"] == 1 and saved["status"] == "draft"
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", data, expected_revision=0)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
    reopened = StructuralProApp(db)
    try:
        saved = reopened.get_aec_system("P", case[0], "L1", "COMP1")
        assert saved["status"] == "draft" and saved["revision"] == 1
        assert saved["data"] == original
        assert reopened.open_project("P")["boq"] == []
    finally:
        reopened.store.close()


@pytest.mark.parametrize("case", CASES)
def test_incomplete_draft_cannot_write_boq(tmp_path, case):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("مصنوعی", "P")
        doc = document(case)
        doc["components"][case[1]] = {"status": "unreviewed"}
        saved = app.save_aec_system_draft("P", doc, expected_revision=0)
        before = deepcopy(app.open_project("P"))
        with pytest.raises((RuntimeError, ValueError)):
            app.commit_aec_system("P", case[0], "L1", "COMP1",
                                  expected_revision=saved["revision"])
        assert app.open_project("P") == before
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()


def test_duplicate_source_id_across_two_site_families_fails_closed(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    try:
        app.create_project("مصنوعی", "P")
        first, second = document(CASES[1]), document(CASES[2])
        second["source"]["source_id"] = first["source"]["source_id"]
        app.save_aec_system_draft("P", first, expected_revision=0)
        snapshot = deepcopy(app.open_project("P"))
        with pytest.raises(ValueError):
            app.save_aec_system_draft("P", second, expected_revision=0)
        assert app.open_project("P") == snapshot
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
