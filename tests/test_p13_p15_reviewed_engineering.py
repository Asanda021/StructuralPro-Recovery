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
    assert sum(r["quantity"] for r in preview["rows"]) == pytest.approx(101+101+75.36)


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



def _reviewed_structural(kind, ident, geometry):
    from core.takeoff.reviewed_structural import empty_member
    d=empty_member(kind, "L1", ident)
    d["source"]={"mode":"manual","source_id":f"manual:{kind}:{ident}"}
    d["geometry"]={"count":1, "source_ref":"plan-section-A2",
                   "approved_by":"structural-checker", "intersections":[], **geometry}
    d["formwork"]={"status":"not_applicable", "reason":"no-contact-formwork per reviewed detail",
                   "source_ref":"detail-A2","approved_by":"checker"}
    for name in d["rebars"]:
        d["rebars"][name]={"status":"not_applicable","reason":"not in the reviewed structural schedule",
                           "source_ref":f"detail-A2:{name}", "approved_by":"checker"}
    return d


def test_round_column_volume_from_real_diameter_without_box_approximation():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("column","C-R",{"shape":"circular_column",
              "diameter":.5,"height":3.0})
    report=preview_member(d,TakeoffEngine())
    assert report["ready"],report["blockers"]
    assert report["rows"][0]["quantity"]==pytest.approx(math.pi*(.5/2)**2*3)


def test_circular_column_requires_diameter_and_rejects_conflicting_box_shape():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("column","C-R",{"shape":"circular_column","height":3})
    assert not preview_member(d,TakeoffEngine())["ready"]
    d["geometry"]["diameter"]=.5
    d["geometry"]["width"]=.5
    assert not preview_member(d,TakeoffEngine())["ready"]


def test_stepped_footing_uses_reviewed_separate_concrete_regions():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("isolated_footing","F-ST",{
        "shape":"reviewed_sections", "sections":[
            {"id":"base","length_m":2,"width_m":2,"thickness_m":.4,
             "source_ref":"F1:base","approved_by":"checker"},
            {"id":"step","length_m":1,"width_m":1,"thickness_m":.3,
             "source_ref":"F1:step","approved_by":"checker"},
        ]})
    report=preview_member(d,TakeoffEngine())
    assert report["ready"], report["blockers"]
    assert report["rows"][0]["quantity"]==pytest.approx(1.9)


def test_duplicate_or_incomplete_footing_sections_never_commit():
    from core.takeoff.reviewed_structural import preview_member
    a={"id":"same","length_m":2,"width_m":2,"thickness_m":.4,
       "source_ref":"detail","approved_by":"checker"}
    d=_reviewed_structural("isolated_footing","F1",{
        "shape":"reviewed_sections","sections":[a,deepcopy(a)]})
    assert not preview_member(d,TakeoffEngine())["ready"]
    d["geometry"]["sections"][1]["id"]="other"
    del d["geometry"]["sections"][1]["source_ref"]
    assert not preview_member(d,TakeoffEngine())["ready"]


def test_approved_variable_height_column_has_explicit_area_of_each_segment():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("column","C1",{"shape":"reviewed_sections","sections":[
        {"id":"L1","net_section_area_m2":.2,"start_m":0,"end_m":2,
         "source_ref":"C1:lower","approved_by":"checker"},
        {"id":"L2","net_section_area_m2":.16,"start_m":2,"end_m":3,
         "source_ref":"C1:upper","approved_by":"checker"},
    ]})
    report=preview_member(d,TakeoffEngine())
    assert report["ready"],report["blockers"]
    assert report["rows"][0]["quantity"]==pytest.approx(.56)



def test_variable_column_rejects_gap_and_overlap_between_sections():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("column","C1",{"shape":"reviewed_sections","sections":[
        {"id":"L1","net_section_area_m2":.2,"start_m":0,"end_m":2,
         "source_ref":"C1:lower","approved_by":"checker"},
        {"id":"L2","net_section_area_m2":.16,"start_m":2.1,"end_m":3,
         "source_ref":"C1:upper","approved_by":"checker"}]})
    assert not preview_member(d, TakeoffEngine())["ready"]
    d["geometry"]["sections"][1]["start_m"]=1.9
    assert not preview_member(d, TakeoffEngine())["ready"]


def test_bored_pile_must_use_real_diameter_and_can_have_independent_rebar_groups():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("bored_pile","P1",{"shape":"circular_column",
                                            "diameter":.6,"height":9})
    report=preview_member(d, TakeoffEngine())
    assert report["ready"],report["blockers"]
    assert report["rows"][0]["quantity"]==pytest.approx(math.pi*.3**2*9)
    assert {"longitudinal", "spiral_ties", "crossties", "starters"} == set(d["rebars"])


def test_pile_cap_is_distinct_from_a_regular_footing():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("pile_cap","PC1",{
        "length":2.4,"width":2.4,"thickness":.7})
    report=preview_member(d,TakeoffEngine())
    assert report["ready"],report["blockers"]
    assert report["rows"][0]["quantity"]==pytest.approx(4.032)


def test_pile_without_diameter_or_shape_is_rejected():
    from core.takeoff.reviewed_structural import preview_member
    d=_reviewed_structural("bored_pile","P1",{"height":9})
    assert not preview_member(d, TakeoffEngine())["ready"]
    d["geometry"]["shape"]="circular_column"
    assert not preview_member(d, TakeoffEngine())["ready"]
