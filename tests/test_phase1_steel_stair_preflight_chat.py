"""Independent steel-stair preflight tests, not AEC/BOQ acceptance."""
from copy import deepcopy
from decimal import Decimal
import pytest

from core.takeoff.steel_stair_preflight import GROUP_UNITS, POLICY, preview


def schedule():
    groups = {name: {"status": "not_applicable", "approved_by": "synthetic-reviewer",
                     "source_ref": "synthetic-scope", "reason": "excluded by signed synthetic detail",
                     "entries": []} for name in GROUP_UNITS}
    groups["stringers"] = {"status": "confirmed", "approved_by": "reviewer",
        "source_ref": "steel-section-detail", "reason": "", "entries": [{
            "id": "ST-STR-01", "source_ref": "steel-section-detail", "approved_by": "reviewer",
            "spec_ref": "profile-catalogue", "scope_ref": "stair-scope-stringer",
            "mode": "steel_profile_schedule", "details": {
                "count": "2", "length_m": "3", "unit_weight_kg_m": "4.5",
                "unit_weight_source": "synthetic-profile-catalogue"}}]}
    groups["treads"] = {"status": "confirmed", "approved_by": "reviewer",
        "source_ref": "tread-detail", "reason": "", "entries": [{
            "id": "ST-TR-01", "source_ref": "tread-detail", "approved_by": "reviewer",
            "spec_ref": "plate-detail", "scope_ref": "stair-scope-tread",
            "mode": "steel_plate_schedule", "details": {
                "count": "10", "length_m": "0.3", "width_m": "0.8",
                "thickness_m": "0.005", "density_kg_m3": "7850",
                "density_source": "synthetic-supplier-datasheet"}}]}
    claims = [{"physical_id": e["id"], "building_id": "BUILDING-A",
               "owner_system": "STAIR-A", "payer_system": "STAIR-A",
               "scope_ref": e["scope_ref"], "source_ref": e["source_ref"],
               "approved_by": "ownership-reviewer"}
              for g in groups.values() for e in g["entries"]]
    return {"kind": "stair_metal", "measurement_policy": POLICY,
            "building_id": "BUILDING-A", "floor_id": "L1", "system_id": "STAIR-A",
            "axis": "A-B", "source": {"plan_ref": "PLAN-A", "detail_ref": "DETAIL-A",
                   "sha256": "1"*64, "source_id": "STAIR-DRAWING-A"},
            "groups": groups, "ownership": {"ledger_ref": "ownership-ledger-A",
                                             "claims": claims}}


def test_sourced_quantities_are_exact_and_never_payable():
    x = schedule(); original = deepcopy(x)
    o = preview(x)
    assert o["engineering_ready"] and not o["ready"] and not o["commit_allowed"]
    assert o["payable_rows"] == [] and o["blockers"]
    assert o["totals_exact"]["kg"] == "121.20000"
    assert Decimal(o["totals_exact"]["kg"]) == Decimal("121.2")
    assert len(o["candidates"]) == 2 and x == original


@pytest.mark.parametrize("field", ["kind", "measurement_policy", "building_id", "floor_id", "system_id", "axis"])
def test_identity_policy_fail_closed(field):
    x = schedule(); x[field] = "" if field != "kind" else "stair"
    o = preview(x)
    assert not o["engineering_ready"] and not o["candidates"] and not o["payable_rows"]


@pytest.mark.parametrize("component", ["stringers", "treads"])
def test_essential_groups_are_never_not_applicable(component):
    x = schedule(); x["groups"][component]["status"] = "not_applicable"
    o = preview(x)
    assert not o["engineering_ready"] and o["payable_rows"] == []


@pytest.mark.parametrize("field", ["unit_weight_source", "length_m", "count"])
def test_profile_schedule_needs_actual_spec(field):
    x = schedule(); x["groups"]["stringers"]["entries"][0]["details"].pop(field)
    assert not preview(x)["engineering_ready"]


@pytest.mark.parametrize("field", ["density_source", "thickness_m", "width_m"])
def test_plate_schedule_requires_signed_source(field):
    x = schedule(); x["groups"]["treads"]["entries"][0]["details"].pop(field)
    assert not preview(x)["engineering_ready"]


@pytest.mark.parametrize("count", ["0", "1.5", "1e1000", "9007199254740993.5"])
def test_unsupported_or_fractional_plate_count_rejected(count):
    x = schedule(); x["groups"]["treads"]["entries"][0]["details"]["count"] = count
    assert not preview(x)["engineering_ready"]


def test_duplicate_physical_id_in_different_groups_rejected():
    x = schedule(); x["groups"]["treads"]["entries"][0]["id"] = "ST-STR-01"
    assert not preview(x)["engineering_ready"]


@pytest.mark.parametrize("edit", ["drop", "duplicate", "payer", "building", "scope", "owner"])
def test_bad_owner_or_payer_claim_never_accepted(edit):
    x = schedule(); cs = x["ownership"]["claims"]
    if edit == "drop": cs.pop()
    elif edit == "duplicate": cs[1]["physical_id"] = cs[0]["physical_id"]
    elif edit == "payer": cs[0]["payer_system"] = "CONCRETE-STAIR-A"
    elif edit == "building": cs[0]["building_id"] = "ANOTHER-BUILDING"
    elif edit == "scope": cs[0]["scope_ref"] = "UNMATCHED-SCOPE"
    elif edit == "owner": cs[0]["owner_system"] = "ANOTHER-STAIR"
    assert not preview(x)["engineering_ready"]


def test_real_zero_quantity_does_not_create_payable_row():
    x = schedule(); x["groups"]["stringers"]["entries"][0]["details"]["length_m"] = "0"
    o = preview(x)
    assert not o["engineering_ready"] and o["payable_rows"] == []


def test_missing_source_hash_is_blocking():
    x = schedule(); x["source"]["sha256"] = "NOT-A-HASH"
    assert not preview(x)["engineering_ready"]


def test_optional_group_requires_explicit_nonapplicability():
    x = schedule(); x["groups"]["bolts"]["reason"] = ""
    assert not preview(x)["engineering_ready"]


def test_profile_method_cannot_be_used_for_piece_unit():
    x = schedule(); e = deepcopy(x["groups"]["stringers"]["entries"][0])
    e["id"] = "ST-ANC-01"
    x["groups"]["anchors"] = {"status": "confirmed", "approved_by": "reviewer",
         "source_ref": "ANCH", "reason": "", "entries": [e]}
    x["ownership"]["claims"].append({"physical_id": "ST-ANC-01",
      "building_id": "BUILDING-A", "owner_system": "STAIR-A", "payer_system": "STAIR-A",
      "scope_ref": e["scope_ref"], "source_ref": "ANCH", "approved_by": "reviewer"})
    assert not preview(x)["engineering_ready"]


def test_measured_piece_count_must_be_whole():
    x = schedule()
    e = deepcopy(x["groups"]["stringers"]["entries"][0])
    e.update(id="ST-ANC-02", mode="measured", details={"quantity":"1.5",
        "unit":"عدد", "measurement_ref":"MEAS", "basis":"documented physical count"})
    x["groups"]["anchors"] = {"status":"confirmed", "approved_by":"reviewer",
        "source_ref":"ANCH", "reason":"", "entries":[e]}
    x["ownership"]["claims"].append({"physical_id":"ST-ANC-02",
        "building_id":"BUILDING-A", "owner_system":"STAIR-A", "payer_system":"STAIR-A",
        "scope_ref":e["scope_ref"], "source_ref":e["source_ref"], "approved_by":"reviewer"})
    assert not preview(x)["engineering_ready"]


def test_claim_reference_must_match_physical_entry():
    x=schedule()
    x["ownership"]["claims"][0]["source_ref"]="ANOTHER-DOCUMENT"
    assert not preview(x)["engineering_ready"]
