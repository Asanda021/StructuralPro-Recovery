"""Bounded 36-family contracts, not whole-family engineering acceptance.

Rows below are an explicit synthetic quantity ledger. Engine references use
independent decimal arithmetic; measured rows only prove faithful preservation
of an explicitly entered measurement, NOT an independent design calculation.
Timber volume and steel stair remain governed by their separate nonfinancial
preflights. No new permission, price, capacity, layout or engineer is invented.
"""
from copy import deepcopy
from decimal import Decimal

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system


# family: component/unit/quantity. All values are test-only explicit inputs.
LEDGER = {
    "kromit_roof": "joists/عدد/3 topping/m3/1.5",
    "composite_roof": "steel_members/kg/27 concrete/m3/1.5",
    "sandwich_roof": "panels/عدد/3",
    "timber_roof": "joists/عدد/3",
    "precast_roof": "precast_units/عدد/3",
    "gypsum_partition": "frames/عدد/3 boards/عدد/3",
    "cement_render": "render_coat/m2/25.15",
    "door_window": "frame/عدد/3",
    "upvc_aluminium_windows": "profiles/m/3.75 glazing/m2/25.15",
    "glass_curtain_wall": "mullions/m/3.75 glazing/m2/25.15",
    "facade_cladding": "panels/عدد/3",
    "handrails_metalwork": "profiles/kg/27",
    "plumbing": "pipes/m/3.75",
    "sanitary_drainage": "pipes/m/3.75",
    "hvac": "equipment/عدد/3",
    "mechanical_ventilation": "ducts/m2/2.25",
    "plantroom": "equipment/عدد/3",
    "natural_gas": "pipes/m/3.75",
    "fire_protection": "pipes/m/3.75",
    "electrical_power": "cables/m/3.75",
    "lighting": "fixtures/عدد/3",
    "low_voltage": "devices/عدد/3",
    "fire_alarm": "detectors/عدد/3 panels/عدد/3",
    "data_network": "cables/m/3.75",
    "security_systems": "controllers/عدد/3",
    "emergency_power": "panels/عدد/3",
    "elevator": "car/عدد/3 machine/عدد/3",
    "external_earthwork": "excavation/m3/3.75",
    "blinding_concrete": "blinding_concrete/m3/0.6",
    "retaining_structures": "soldier_piles/عدد/3",
    "external_works": "paving/m2/3.75",
    "site_drains": "pipes/m/3.75",
    "demolition": "selective_demolition/m3/3.75",
    "concrete_repair": "repair_mortar/m3/3.75",
    "seismic_retrofit": "anchorage/عدد/3",
    "historic_restoration": "documentation/عدد/3 stabilization/m2/3.75",
}


def document(family):
    domain = ("mechanical" if family in {"plumbing", "sanitary_drainage", "hvac", "mechanical_ventilation", "plantroom", "natural_gas", "fire_protection"}
              else "electrical" if family in {"electrical_power", "lighting", "low_voltage", "fire_alarm", "data_network", "security_systems", "emergency_power", "elevator"}
              else "civil" if family in {"external_earthwork", "retaining_structures", "external_works", "site_drains"}
              else "advanced" if family == "blinding_concrete" else "building")
    d = empty_system(family, "L1", "SYNTHETIC-MEMBER")
    d["source"] = {"mode": "manual", "source_id": "SYNTHETIC:" + family, "revision": "SYN-R1"}
    for name in d["components"]:
        d["components"][name] = dict(status="not_applicable", reason="Explicit exclusion from this synthetic subset only",
                                     source_ref="SYNTHETIC:SCOPE:R1", approved_by="SYNTHETIC_TEST_ONLY")
    expected = {}
    for text in LEDGER[family].split():
        name, unit, value = text.split("/")
        expected[name] = (Decimal(value), unit)
        item = dict(line_id="LINE-" + name, source_ref="SYNTHETIC:MEASUREMENT:R1",
                    spec_ref="SYNTHETIC:SPEC:R1", description="Explicit synthetic " + name,
                    domain=domain, item_code="TEST-" + name, mode="measured",
                    quantity=value, unit=unit, formula="Explicit supplied measurement; no design inference",
                    measurement_ref="SYNTHETIC:TRACE:" + name)
        route = {"pipes": "pipe", "cables": "cable", "equipment": "equipment",
                 "fixtures": "light"}.get(name)
        if family in {"fire_alarm", "emergency_power"} and name == "panels":
            route = "panel"
        if route and domain in {"mechanical", "electrical"}:
            params = {"count": "3", "length": "1.25"} if route in {"pipe", "cable"} else {"count": "3"}
            oracle = Decimal("3") * Decimal("1.25") if "length" in params else Decimal("3")
            assert oracle == Decimal(value)
            item.update(mode="engine", item=route, params=params)
        if family == "mechanical_ventilation":
            item.update(mode="engine", item="duct_area", params=dict(width="0.125", height="0.375", length="2.25"))
            assert Decimal(value) == 2 * (Decimal("0.125") + Decimal("0.375")) * Decimal("2.25")
        if family == "blinding_concrete":
            item.update(mode="engine", item="footing_concrete", params=dict(length="3", width="2", thickness="0.1", count="1"))
            assert Decimal(value) == Decimal("3") * Decimal("2") * Decimal("0.1")
        detail = None
        fields = {}
        if name in {"topping", "concrete"}:
            detail, fields = "rectangle_volume", dict(count="2", length_m="2", width_m="1.5", thickness_m="0.25")
            assert Decimal(value) == 2 * Decimal("2") * Decimal("1.5") * Decimal("0.25")
        if name in {"render_coat", "glazing"}:
            detail, fields = "net_surface", dict(count="2", length_m="4.8", width_m="2.75", openings_m2="1.25")
            assert Decimal(value) == 2 * Decimal("4.8") * Decimal("2.75") - Decimal("1.25")
        if name == "steel_members" or (family == "handrails_metalwork" and name == "profiles"):
            detail, fields = "steel_profile_schedule", dict(count="2", length_m="3", unit_weight_kg_m="4.5", unit_weight_source="SYNTHETIC:CATALOG:R1")
            assert Decimal(value) == 2 * Decimal("3") * Decimal("4.5")
        if family in {"precast_roof", "sandwich_roof", "kromit_roof"} and name in {"precast_units", "panels", "joists"}:
            detail, fields = "piece_schedule", dict(count="3", spec_ref="SYNTHETIC:PIECES:R1")
        if detail:
            item.update(mode="detail", detail_type=detail,
                        details={"entries": [dict(id="PHYSICAL-" + name, source_ref="SYNTHETIC:DIMENSIONS:R1",
                                                   approved_by="SYNTHETIC_TEST_ONLY", **fields)]})
        d["components"][name] = dict(status="confirmed", approved_by="SYNTHETIC_TEST_ONLY", items=[item])
    assert set(expected) == set(SPECS[family].essential)
    return d, expected


@pytest.mark.parametrize("family", LEDGER)
def test_family_bounded_oracle_reopen_edit_stale_cas_and_nonempty_boq(tmp_path, family):
    draft, expected = document(family)
    app = StructuralProApp(tmp_path)
    try:
        app.create_project("Synthetic bounded ledger", "P")
        app.add_takeoff("P", "building", "column", source_id="SYNTHETIC:EXISTING-BOQ", system="OTHER",
                        manual_location_id="COL", count=1, width=0.4, depth=0.4, height=3)
        baseline = app.open_project("P")
        assert baseline["boq"] and baseline["takeoffs"]
        app.save_aec_system_draft("P", draft, expected_revision=0)
    finally:
        app.store.close()
    reopened = StructuralProApp(tmp_path)
    try:
        assert reopened.get_aec_system("P", family, "L1", "SYNTHETIC-MEMBER")["data"] == draft
        result = reopened.preview_aec_system("P", family, "L1", "SYNTHETIC-MEMBER")
        assert result["ready"], result["blockers"]
        assert len(result["rows"]) == len(expected)
        for row in result["rows"]:
            quantity, unit = expected[row["component"]]
            assert row["unit"] == unit
            assert abs(Decimal(str(row["quantity"])) - quantity) <= Decimal("1e-12")
        edited = deepcopy(draft)
        for part in edited["components"].values():
            part["status"] = "unreviewed"
        reopened.save_aec_system_draft("P", edited, expected_revision=1)
        digest = reopened.store.current_digest("P")
        with pytest.raises(RuntimeError):
            reopened.save_aec_system_draft("P", draft, expected_revision=1)
        with pytest.raises(ValueError):
            reopened.commit_aec_system("P", family, "L1", "SYNTHETIC-MEMBER", expected_revision=2)
        assert reopened.store.current_digest("P") == digest
        for field in ("boq", "takeoffs"):
            assert reopened.open_project("P")[field] == baseline[field]
        assert reopened.store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reopened.store.close()


@pytest.mark.parametrize("family", LEDGER)
@pytest.mark.parametrize("fault", ["source", "zero", "unit", "duplicate"])
def test_family_bad_subset_exposes_no_quantities(family, fault):
    draft, expected = document(family)
    part = draft["components"][next(iter(expected))]
    item = part["items"][0]
    if fault == "source":
        draft["source"] = {}
    elif fault == "duplicate":
        part["items"].append(deepcopy(item))
    elif fault == "unit":
        item.update(mode="measured", unit="INVALID_UNIT")
    elif item["mode"] == "engine":
        item["params"][next(iter(item["params"]))] = "0"
    elif item["mode"] == "detail":
        item["details"]["entries"][0]["count"] = "0"
    else:
        item["quantity"] = "0"
    result = preview_system(draft, TakeoffEngine())
    assert not result["ready"] and result["rows"] == []
