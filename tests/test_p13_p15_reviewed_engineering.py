"""P13–P15 acceptance tests: manual systems, real slabs, steel and timber."""
from __future__ import annotations

from copy import deepcopy
import math
import pytest

from core.takeoff.reviewed_detail_calculators import calculate_reviewed_detail
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system, ReviewedAECWorkflow
from core.takeoff.manual_input import parse_manual_entry
from core.takeoff.manual_workbench import ManualTakeoffWorkbench, ManualTakeoffDraft
from core.takeoff.assembly_templates import AssemblyTemplateLibrary
from core.engineering.domains.steel import steel_quantities
from core.projects.store import ProjectStore
from core.takeoff.engine import TakeoffEngine


def entry(kind, **values):
    return {"id": "L1", "source_ref": "approved-sheet-A1",
            "approved_by": "checker", **values}


def result(kind, rows):
    return calculate_reviewed_detail(kind, {"entries": rows})


@pytest.mark.parametrize("kind,rows,amount,unit", [
    ("rectangle_volume", [entry("concrete", count=2, length_m=5,
                                width_m=.3, thickness_m=.2)], .6, "m3"),
    ("net_surface", [entry("formwork", count=2, length_m=5, width_m=3,
                          openings_m2=4)], 26, "m2"),
    ("steel_profile_schedule", [entry("steel", count=2, length_m=6,
                                      unit_weight_kg_m=18.8,
                                      unit_weight_source="reviewed-profile-catalog")], 225.6, "kg"),
    ("steel_plate_schedule", [entry("plate", count=3, length_m=.3,
                                    width_m=.2, thickness_m=.01,
                                    density_kg_m3=7850, density_source="supplier-certificate")], 14.13, "kg"),
    ("timber_volume_schedule", [entry("timber", count=4, length_m=3,
                                     width_m=.1, depth_m=.2)], .24, "m3"),
    ("piece_schedule", [entry("bolts", count=16, spec_ref="reviewed-schedule")], 16, "عدد"),
    ("concrete_regions", [entry("roof", length_m=5, width_m=4, thickness_m=.2,
                               voids=[{"id": "void-01", "volume_m3": .5,
                                       "source_ref": "roof-detail", "approved_by": "checker"}])], 3.5, "m3"),
])
def test_reviewed_detail_golden_values(kind, rows, amount, unit):
    output = result(kind, rows)
    assert output["quantity"] == pytest.approx(amount)
    assert output["unit"] == unit
    assert output["details"][0]["approved_by"] == "checker"


@pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan"), True])
def test_steel_mass_never_accepts_invalid_weights(bad):
    with pytest.raises(ValueError):
        result("steel_profile_schedule",
               [entry("steel", count=2, length_m=6,
                      unit_weight_kg_m=bad, unit_weight_source="catalog")])


def test_no_default_plate_density():
    with pytest.raises(ValueError):
        result("steel_plate_schedule", [entry("plate", count=1,
               length_m=1, width_m=1, thickness_m=.02)])


def test_no_default_piece_count_and_specification():
    with pytest.raises(ValueError):
        result("piece_schedule", [entry("bolts", count=1)])
    with pytest.raises(ValueError):
        result("piece_schedule", [entry("bolts", spec_ref="approved")])


def test_no_default_timber_dimensions():
    with pytest.raises(ValueError):
        result("timber_volume_schedule", [entry("wood", count=1, length_m=4, width_m=.1)])


def test_no_duplicate_physical_member_identity():
    one = entry("steel", count=2, length_m=6, unit_weight_kg_m=18,
                unit_weight_source="catalog")
    with pytest.raises(ValueError, match="تکراری"):
        result("steel_profile_schedule", [one, deepcopy(one)])


def test_region_voids_cannot_be_reused_across_multiple_roof_regions():
    v = {"id": "void-Z", "volume_m3": .2,
         "source_ref": "plan", "approved_by": "checker"}
    a = entry("roof", length_m=5, width_m=4, thickness_m=.2, voids=[v])
    b = entry("roof", length_m=5, width_m=4, thickness_m=.2, voids=[v])
    b["id"] = "L2"
    with pytest.raises(ValueError, match="دوبار"):
        result("concrete_regions", [a, b])


def test_region_void_greater_than_concrete_is_invalid():
    with pytest.raises(ValueError):
        result("concrete_regions", [entry("roof", length_m=1, width_m=1,
                             thickness_m=.1,
                             voids=[{"id":"1", "volume_m3":.2,
                                     "source_ref":"plan", "approved_by":"checker"}])])


def test_unknown_or_hidden_extra_detail_fields_are_rejected():
    with pytest.raises(ValueError):
        result("rectangle_volume", [entry("roof", count=1, length_m=4,
             width_m=3, thickness_m=.2, hidden_waste_factor=1.1)])


def reviewed(kind, sid="X1"):
    d=empty_system(kind, "L1", sid)
    d["source"]={"mode":"manual", "source_id":f"manual:{kind}:L1:{sid}"}
    for component in SPECS[kind].components:
        d["components"][component] = {
            "status":"not_applicable", "reason":"explicitly absent per reviewed plan",
            "source_ref":f"sheet-{kind}-{component}", "approved_by":"checker"}
    return d


def detail_part(component, method, rows):
    return {"status":"confirmed", "approved_by":"checker", "items":[{
        "line_id":f"{component}-line", "item_code":component,
        "description":f"جزئیات {component}", "domain":"building",
        "mode":"detail", "detail_type":method, "details":{"entries":rows},
        "source_ref":f"sheet-A1:{component}"}]}


def test_steel_frame_tons_are_per_component_not_one_assumed_steel_weight():
    d=reviewed("steel_frame")
    for name in ("columns","beams"):
        d["components"][name] = detail_part(name,"steel_profile_schedule",[
            entry(name, count=2, length_m=5, unit_weight_kg_m=10.1,
                  unit_weight_source="certified-table")])
    d["components"]["plates"]=detail_part("plates","steel_plate_schedule",[
        entry("plates", count=8, length_m=.2, width_m=.3, thickness_m=.02,
              density_kg_m3=7850, density_source="certified-plate-density")])
    preview=preview_system(d,TakeoffEngine())
    assert preview["ready"], preview["blockers"]
    assert len(preview["rows"]) == 3
    assert {r["unit"] for r in preview["rows"]} == {"kg"}
    assert sum(r["quantity"] for r in preview["rows"]) == pytest.approx(202+202+75.36)


def test_composite_concrete_and_steel_are_separate_material_rows():
    d=reviewed("composite_frame")
    d["components"]["steel"]=detail_part("steel","steel_profile_schedule",[
        entry("I-beam", count=1, length_m=5, unit_weight_kg_m=29,
              unit_weight_source="approved-catalog")])
    d["components"]["concrete"]=detail_part("concrete","rectangle_volume",[
        entry("encasement", count=1, length_m=5,width_m=.35,thickness_m=.2)])
    preview=preview_system(d,TakeoffEngine())
    assert preview["ready"],preview["blockers"]
    assert {(r["unit"],r["quantity"]) for r in preview["rows"]} == {("kg",145),("m3",.35)}


def test_timber_members_measured_in_real_volume():
    d=reviewed("timber_frame")
    d["components"]["members"]=detail_part("members","timber_volume_schedule",[
        entry("wood",count=4,length_m=3,width_m=.1,depth_m=.2)])
    preview=preview_system(d,TakeoffEngine())
    assert preview["ready"],preview["blockers"]
    assert preview["rows"][0]["quantity"] == pytest.approx(.24)
    assert preview["rows"][0]["unit"] == "m3"


def test_uboot_voids_must_not_be_subtracted_twice():
    d=reviewed("uboot")
    d["components"]["gross_concrete"]=detail_part("gross_concrete","concrete_regions",[
        entry("bay",length_m=5,width_m=4,thickness_m=.3,
              voids=[{"id":"bad","volume_m3":1,"source_ref":"v","approved_by":"checker"}])])
    d["components"]["verified_voids"] = {"status":"confirmed","approved_by":"checker",
        "items":[{"line_id":"void", "item_code":"voids", "description":"حفره",
                  "mode":"measured","quantity":1,"unit":"m3",
                  "source_ref":"void-drawing","measurement_ref":"void:1",
                  "formula":"حجم حفره تأییدشده","domain":"building"}]}
    assert not preview_system(d,TakeoffEngine())["ready"]


def test_unknown_group_does_not_become_zero_or_auto_approved():
    d=reviewed("steel_frame")
    d["components"]["columns"]={"status":"unreviewed"}
    d["components"]["beams"]=detail_part("beams","steel_profile_schedule",[
        entry("beam", count=1, length_m=6,unit_weight_kg_m=12,unit_weight_source="catalog")])
    assert not preview_system(d,TakeoffEngine())["ready"]


def test_manual_joist_parser_and_workbench_require_explicit_physical_count():
    line=("تیرچه بلوک: تعداد=1 طول=5m عرض=6m ضخامت رویه=0.05m "
          "فاصله تیرچه=0.5m عرض تیرچه=0.1m عمق تیرچه=0.2m")
    parsed=parse_manual_entry(line)
    assert "joist_count" in parsed.missing
    wb=ManualTakeoffWorkbench("P1")
    assert isinstance(wb.add_text(line, floor_id="L1"),ManualTakeoffDraft)
    extended=line+" تعداد تیرچه=13"
    parsed=parse_manual_entry(extended)
    assert parsed.params["joist_count"] == 13
    assert not parsed.missing


@pytest.mark.parametrize("code", ("joist_foam_roof_assembly", "joist_block_roof_assembly"))
def test_roof_assembly_templates_require_joist_count(code):
    template=AssemblyTemplateLibrary().get(code)
    assert "joist_count" in template.required_inputs
    assert "joist_count" not in template.optional_inputs


def test_steel_domain_quantity_is_explicit_for_bolts_and_profiles():
    with pytest.raises(KeyError):
        steel_quantities("beam", length=6, unit_weight=20)
    assert steel_quantities("beam", length=6, unit_weight=20, count=2).quantity == 240
    assert steel_quantities("bolt", quantity=12).quantity == 12
    with pytest.raises(KeyError):
        steel_quantities("bolt")
    with pytest.raises(KeyError):
        steel_quantities("weld", length=4, weld_unit_weight=.2)


def test_atomic_aec_steel_and_timber_boq_sqlite(tmp_path):
    store=ProjectStore(tmp_path/"projects.db")
    store.save("P1",{"id":"P1","name":"نمونه","takeoffs":[],"boq":[]})
    wf=ReviewedAECWorkflow(store,TakeoffEngine())
    for kind,method,name,series in [
        ("steel_frame","steel_profile_schedule","columns",
         entry("column",count=1,length_m=3,unit_weight_kg_m=20,
               unit_weight_source="certified-catalog")),
        ("timber_frame","timber_volume_schedule","members",
         entry("wood",count=3,length_m=2,width_m=.1,depth_m=.1))
    ]:
        d=reviewed(kind)
        if kind=="steel_frame":
            d["components"]["beams"]=detail_part("beams","steel_profile_schedule",[
                entry("beam",count=1,length_m=5,unit_weight_kg_m=15,
                      unit_weight_source="catalog")])
        d["components"][name]=detail_part(name,method,[series])
        wf.save_draft("P1",d,expected_revision=0)
        output=wf.commit("P1",kind,"L1","X1",expected_revision=1)
        assert output["status"]=="committed"
    saved=store.get("P1")
    assert len(saved["boq"])==len(saved["takeoffs"])==3
    assert {x["unit"] for x in saved["boq"]} == {"kg","m3"}
    store.close()
