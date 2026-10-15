"""Synthetic independent rectangular void-cell acceptance for U-Boot/Cobiax.

Not an engineering designer, manufacturer certificate, Windows acceptance, or
permission to cut/cross a void former. This module MUST be executed by pytest
before claiming acceptance; existence alone is not a green test run.
"""
from copy import deepcopy
from decimal import Decimal
import pytest

from core.takeoff.reviewed_aec import empty_system, preview_system
from core.takeoff.engine import TakeoffEngine
from test_roof_specialist_work import sample as base_sample

KINDS = ("uboot", "cobiax")


def sample(kind="uboot"):
    assert kind in KINDS
    d = base_sample("solid_slab")
    d.update(kind=kind, components=empty_system(kind, "L1", "S1")["components"])
    d["source"]["source_id"] = "SYNTHETIC-" + kind
    rd = d["roof_detail"]
    g = rd["geometry"]
    g.pop("action", None)
    g.update(depth=".3", topping_thickness=".05", bottom_thickness=".05")
    def box(i,component,x,y,z,length,width,height):
        return {
            "id":i,"component":component,"x":str(x),"y":str(y),"z":str(z),
            "length":str(length),"width":str(width),"height":str(height),
            "source_ref":"پلان مستند مصنوعی","approved_by":"بازبین مصنوعی",
        }
    rd["regions"]=[
        box("BOTTOM","solid_zones",0,0,0,4,4,".05"),
        box("TOP","topping",0,0,".25",4,4,".05"),
        box("CELL","void",0,0,".05",2,2,".2"),
        box("RIB1","solid_zones",2,0,".05",2,4,".2"),
        box("RIB2","solid_zones",0,2,".05",2,2,".2"),
    ]
    uboot = kind=="uboot"
    former = {
        "id":"FORMER-1","physical_key":"physical-former-1",
        "region_id":"CELL","shape":"rectangular_prism" if uboot else "certified_sphere",
        "count":"1","x":".1" if uboot else ".5",
        "y":".1" if uboot else ".5","z":".06" if uboot else ".075",
        "length":"1.8" if uboot else ".15",
        "width":"1.8" if uboot else ".15",
        "height":".18" if uboot else ".15",
        "diameter_m":"" if uboot else ".15",
        "certified_void_volume_m3":".5832" if uboot else ".0017",
        "volume_source_ref":"گواهی مصنوعی حجم واقعی حفره",
        "spec_ref":"گواهی مصنوعی نوع قطعه",
        "source_ref":"جانمایی مستقل مصنوعی",
        "approved_by":"بازبین دیتایل مصنوعی",
    }
    rd["void_formers"]=[former]
    for group in ("thermal","solid"):
        part=deepcopy(rd["rebars"]["main_x"])
        part["series"][0].update(
            id="B-"+group,physical_key="physical-"+group,
        )
        rd["rebars"][group]=part
    return d


def amounts(kind):
    result=preview_system(sample(kind), TakeoffEngine())
    assert result["ready"],result["blockers"]
    totals={}
    for r in result["rows"]:
        totals[r["item_code"]]=totals.get(r["item_code"],Decimal(0))+Decimal(str(r["quantity"]))
    return totals,result


@pytest.mark.parametrize(("kind","net"),[
    ("uboot","4.2168"),("cobiax","4.7983"),
])
def test_independent_concrete_reference_no_double_void_deduction(kind,net):
    totals,result=amounts(kind)
    assert totals["concrete"]==Decimal(net)
    assert totals["void_formers"]==Decimal(1)
    assert totals["formwork"]==Decimal(16)
    assert totals["rebar"]==Decimal("142.08")
    assert all(r["role"]=="work" for r in result["rows"])
    certified=Decimal("4.8")-Decimal(net)
    cells=[r for r in result["rows"] if r["component"]=="void_cells"]
    assert len(cells)==1
    assert Decimal(str(cells[0]["params"]["deducted_m3"]))==certified


@pytest.mark.parametrize("kind",KINDS)
@pytest.mark.parametrize("operation",["sqlite_amendment_and_boq","copy_delete_and_reports"])
def test_common_sqlite_revision_boq_backup_and_four_reports(tmp_path,kind,operation,monkeypatch):
    import test_roof_specialist_work as base
    monkeypatch.setattr(base,"sample",sample)
    getattr(base,"test_"+operation)(tmp_path,kind)


@pytest.mark.parametrize("kind",KINDS)
@pytest.mark.parametrize("fault",[
    "missing_former","wrong_count","unknown_shape","no_certificate","zero_void",
    "oversized_void","wrong_region","outside_cell","duplicate_physical",
    "missing_bottom","wrong_bottom","wrong_top","cell_overlap","unpartitioned",
    "cut_former","drawing_source","factory_bar","unknown_field","orphan_piece",
])
def test_void_cell_fail_closed(kind,fault):
    d=sample(kind);rd=d["roof_detail"];g=rd["geometry"];former=rd["void_formers"][0]
    if fault=="missing_former":rd["void_formers"]=[]
    elif fault=="wrong_count":former["count"]="2"
    elif fault=="unknown_shape":former["shape"]="assumed_other"
    elif fault=="no_certificate":former["volume_source_ref"]=""
    elif fault=="zero_void":former["certified_void_volume_m3"]="0"
    elif fault=="oversized_void":former["certified_void_volume_m3"]="1"
    elif fault=="wrong_region":former["region_id"]="RIB1"
    elif fault=="outside_cell":former["x"]="3"
    elif fault=="duplicate_physical":former["physical_key"]="physical-main_x"
    elif fault=="missing_bottom":g.pop("bottom_thickness")
    elif fault=="wrong_bottom":g["bottom_thickness"]=".04"
    elif fault=="wrong_top":g["topping_thickness"]=".04"
    elif fault=="cell_overlap":rd["regions"][3]["x"]="1.9"
    elif fault=="unpartitioned":rd["regions"].pop()
    elif fault=="cut_former":
        rd["deductions"]=[dict(id="OPEN",kind="opening",owner_source_id="",x="1",y="1",z="0",length=".5",width=".5",height=".3",source_ref="برش مصنوعی",approved_by="بازبین مصنوعی")]
    elif fault=="drawing_source":d["source"]["mode"]="drawing"
    elif fault=="factory_bar":rd["rebars"]["thermal"]["series"][0]["supply_scope"]="factory"
    elif fault=="unknown_field":former["inferred_spacing"]="0.2"
    elif fault=="orphan_piece":rd["pieces"]=[{"id":"illicit"}]
    result=preview_system(d,TakeoffEngine())
    assert not result["ready"],(kind,fault,result["rows"])


@pytest.mark.parametrize("kind",KINDS)
def test_missing_rebar_required_group_or_certified_volume_is_never_zero(kind):
    d=sample(kind);d["roof_detail"]["rebars"]["main_y"]["status"]="unreviewed"
    assert not preview_system(d,TakeoffEngine())["ready"]
    d=sample(kind);d["roof_detail"]["void_formers"][0].pop("certified_void_volume_m3")
    assert not preview_system(d,TakeoffEngine())["ready"]


@pytest.mark.parametrize("kind",KINDS)
def test_certified_volume_follows_exact_decimals_not_default_sphere_formula(kind):
    d=sample(kind)
    d["roof_detail"]["geometry"]["count"]="3"
    preview=preview_system(d,TakeoffEngine())
    assert preview["ready"],preview["blockers"]
    totals={}
    for r in preview["rows"]:
        totals[r["item_code"]]=totals.get(r["item_code"],Decimal(0))+Decimal(str(r["quantity"]))
    baseline=Decimal("4.2168" if kind=="uboot" else "4.7983")
    assert totals["concrete"]==3*baseline and totals["void_formers"]==3
