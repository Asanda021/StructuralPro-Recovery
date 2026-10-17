"""Integration-preparation tests: no writes to Work's branch or ProjectStore."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import pytest

from core.takeoff.shear_wall_bridge_chat import compile_preview, BRIDGE_POLICY, ShearBridgeError
from core.takeoff.shear_wall_specialist_chat import ShearWallValidationError

REFERENCE = Path(__file__).resolve().parents[1] / "examples/shear_wall_chat_reference.json"


def sample():
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def preview(data=None, project=None, **kwargs):
    return compile_preview(data or sample(), {"id": "P", "takeoffs": []} if project is None else project,
                           reviewer="Independent Reviewer", review_reference="signed independent synthetic allocation", **kwargs)


def test_exact_net_totals_positive_rows_and_no_double_payment():
    result = preview()
    assert result["status"] == "preview_only_not_integrated"
    assert result["commit_allowed"] is False
    assert len(result["blockers"]) == 2
    assert result["policy"] == BRIDGE_POLICY
    assert result["totals"]["net_concrete_m3"] == "3.5"
    assert result["totals"]["payable_formwork_m2"] == "28"
    assert result["totals"]["rebar_kg"] == "84.944"
    assert len(result["preview_rows"]) == len(result["takeoff_candidates"]) == 5
    assert set(result["excluded_nonpayable_kinds"]) == {"concrete_gross", "concrete_opening_deduction"}
    assert len([r for r in result["preview_rows"] if r["item_code"] == "shear_wall_concrete"]) == 1
    assert sum(Decimal(r["quantity"]) for r in result["preview_rows"] if r["unit"] == "m3") == Decimal("3.5")
    assert sum(Decimal(r["quantity"]) for r in result["preview_rows"] if r["unit"] == "m2") == Decimal("28")
    assert sum(Decimal(r["quantity"]) for r in result["preview_rows"] if r["unit"] == "kg") == Decimal("84.944")
    assert all(Decimal(r["quantity"]) > 0 and r["role"] == "work" for r in result["preview_rows"])
    assert all(q["quantities"][0]["role"] == "work" and q["quantities"][0]["unit_price"] is None for q in result["takeoff_candidates"])
    concrete = next(x for x in result["preview_rows"] if x["item_code"] == "shear_wall_concrete")
    assert concrete["params"]["gross_concrete_m3"] == "3.75"
    assert len(concrete["params"]["intersections"]) == 1
    assert concrete["params"]["intersections"][0]["volume_m3"] == "0.25"


def test_no_mutation_of_source_or_project():
    data, project = sample(), {"id": "P", "takeoffs": [], "boq": []}
    before_data, before_project = deepcopy(data), deepcopy(project)
    preview(data, project)
    assert data == before_data and project == before_project


@pytest.mark.parametrize("reason", ["missing_reviewer", "missing_reference", "self_review", "bad_project_id", "missing_project_id"])
def test_review_and_project_gate(reason):
    data, project = sample(), {"id": "P", "takeoffs": []}
    kw = {"reviewer": "Independent Reviewer", "review_reference": "review evidence"}
    if reason == "missing_reviewer":
        kw["reviewer"] = None
    elif reason == "missing_reference":
        kw["review_reference"] = ""
    elif reason == "self_review":
        kw["reviewer"] = data["source"]["approved_by"]
    elif reason == "bad_project_id":
        project["id"] = "OTHER"
    elif reason == "missing_project_id":
        del project["id"]
    with pytest.raises((ShearBridgeError, ValueError)):
        compile_preview(data, project, **kw)


@pytest.mark.parametrize("conflict", ["same_source", "old_generic", "old_physical_wall", "old_takeoff", "duplicate_row", "invalid_register"])
def test_read_only_collision_preflight(conflict):
    data = sample()
    project = {"id": "P", "takeoffs": []}
    record = {"data": {"kind": "shear_wall", "floor_id": "L1", "system_id": "OLD", "geometry": {"physical_wall_id": "OTHER"}, "source": {"source_id": "OLD-SOURCE"}}, "status": "draft"}
    if conflict == "same_source":
        record["data"]["source"]["source_id"] = data["source"]["source_id"]
        project["reviewed_aec_systems"] = {"a": record}
    elif conflict == "old_generic":
        record["data"]["system_id"] = data["wall_id"]
        project["reviewed_aec_systems"] = {"a": record}
    elif conflict == "old_physical_wall":
        record["data"]["geometry"]["physical_wall_id"] = data["physical_wall_id"]
        project["reviewed_aec_systems"] = {"a": record}
    elif conflict == "old_takeoff":
        project["takeoffs"].append({"source_id": "EXISTING", "params": {"physical_wall_id": data["physical_wall_id"]}})
    elif conflict == "duplicate_row":
        project["takeoffs"].append({"source_id": "aec:shear_wall:L1:SW01:concrete_net:p1", "params": {}})
    else:
        project["reviewed_aec_systems"] = {"a": {"data": "NOT-A-DICT"}}
    with pytest.raises(ValueError):
        preview(data, project)


def test_nonpayable_formwork_face_is_not_exported_as_zero():
    data = sample()
    face = data["formwork"]["main_faces"][1]
    face["status"] = "not_required"
    face["reason"] = "سطح تماس مستقل مستند در این حالت فرضی"
    r = preview(data)
    assert sum(Decimal(x["quantity"]) for x in r["preview_rows"] if x["unit"] == "m2") == Decimal("14")
    assert len(r["preview_rows"]) == 4


def test_cross_member_interface_is_evidence_only_not_assumed_cleared():
    data = sample()
    data["interfaces"].append(dict(id="joint-1", segment_id="P1", foreign_member_id="C1", x_m="3", y_m="0", z_m=".5", width_m=".5", depth_m=".1", height_m="1", deduction_owner="shear_wall", common_datum_ref="CS1", source_ref="contact/C1", approved_by="کارشناس مصنوعی"))
    data["formwork"]["main_faces"][0]["contact_rectangles"] = [dict(id="joint-contact", x_m="3", z_m=".5", width_m=".5", height_m="1", source_ref="contact/face", approved_by="کارشناس مصنوعی")]
    result = preview(data)
    concrete = next(r for r in result["preview_rows"] if r["item_code"] == "shear_wall_concrete")
    assert Decimal(concrete["quantity"]) == Decimal("3.45")
    assert len(concrete["params"]["intersections"]) == 2
    assert result["commit_allowed"] is False
    assert any("ستون" in item for item in result["blockers"])


@pytest.mark.parametrize("fault", ["nan", "float", "missing_bar", "duplicate_parts", "invalid_opening", "negative_thickness"])
def test_engine_adversarial_inputs_still_fail_closed(fault):
    data = sample()
    if fault == "nan": data["segments"][0]["height_m"] = "NaN"
    if fault == "float": data["segments"][0]["height_m"] = 3.0
    if fault == "missing_bar": data["rebars"]["vertical"]["series"] = []
    if fault == "duplicate_parts": data["segments"].append(deepcopy(data["segments"][0]))
    if fault == "invalid_opening": data["openings"][0]["width_m"] = "10"
    if fault == "negative_thickness": data["segments"][0]["thickness_m"] = "-0.25"
    with pytest.raises((ShearWallValidationError, ValueError)):
        preview(data)


def test_very_long_decimal_mass_preserved_as_string():
    data = sample()
    data["rebars"]["horizontal"]["series"][0]["unit_weight_kg_m"] = "0.888000000000000001"
    result = preview(data)
    exact = Decimal("84.944000000000000020")
    assert Decimal(result["totals"]["rebar_kg"]) == exact
    assert sum(Decimal(x["quantity"]) for x in result["preview_rows"] if x["unit"] == "kg") == exact


def test_takeoff_candidates_rejected_by_incoming_duplicate_physical_deduction():
    data = sample()
    r = preview(data)
    assert r["preview_rows"]
    # Even with correct candidate shape, an incoming duplication of deduction ID fails.
    project = {"id": "P", "takeoffs": [
        {"source_id": "OTHER-PROVENANCE", "params": {"intersections": [
            {"id": r["takeoff_candidates"][0]["params"]["intersections"][0]["id"]}
        ]}}
    ]}
    with pytest.raises(ValueError):
        preview(data, project)


def test_in_memory_boq_rebuild_preserves_exacts_and_does_not_persist():
    from core.takeoff.commit_guards import rebuild_project_boq
    data = sample()
    original = {"id": "P", "takeoffs": [], "boq": [], "metadata": {"offline": True}}
    before = deepcopy(original)
    out = preview(data, original)
    proposed, boq = rebuild_project_boq(original, out["takeoff_candidates"])
    assert len(proposed) == 5
    assert len(boq) == 4  # 4 payable operations; zeros and deductions not paid
    for unit, amount in (("m3", "3.5"), ("m2", "28"), ("kg", "84.944")):
        assert sum(Decimal(str(r["quantity"])) for r in boq if r["unit"] == unit) == Decimal(amount)
    assert all(r["unit_price"] is None for r in boq)
    assert original == before
    assert out["commit_allowed"] is False


def test_independence_checks_nested_bar_and_formwork_approvals():
    data = sample()
    data["rebars"]["vertical"]["series"][0]["cut_parts"][0]["approved_by"] = "Independent Reviewer"
    with pytest.raises(ShearBridgeError, match="بازبین"):
        preview(data)
    data = sample()
    data["formwork"]["edge_scope"]["approved_by"] = "Independent Reviewer"
    with pytest.raises(ShearBridgeError, match="بازبین"):
        preview(data)
