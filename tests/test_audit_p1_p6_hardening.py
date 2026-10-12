import pytest
from core.takeoff.construction_core import ConstructionQuantityCore, validate_quantity_lines
from core.takeoff.element_model import ConstructionElement
from core.drawing.measurement_pipeline import DrawingMeasurementGate
from core.drawing.adapters import AdapterResult, DrawingSource
from core.drawing.models import DrawingPrimitive
from core.bim.model import BIMElement
from core.takeoff.boq import build_boq, boq_summary

def test_finish_waste_is_applied_once():
    e=ConstructionElement("F1","finish",length_m=10,height_m=3)
    line=ConstructionQuantityCore.finish_area(e,"FIN","finish",openings_m2=2,waste_rate=.1)
    assert line.quantity==pytest.approx(28)
    assert line.gross_quantity==pytest.approx(30.8)

def test_duplicate_source_is_rejected_but_distinct_sources_are_valid():
    e1=ConstructionElement("E1","wall",length_m=2,source_id="S1")
    e2=ConstructionElement("E2","wall",length_m=2,source_id="S2")
    a=ConstructionQuantityCore.linear_material(e1,"civil","A","a")
    b=ConstructionQuantityCore.linear_material(e2,"civil","B","b")
    assert validate_quantity_lines([a,b])["ok"]
    assert not validate_quantity_lines([a, b.__class__(b.element_id,b.domain,b.item_code,b.description,b.quantity,b.unit,b.formula,"S1",b.waste_rate,b.gross_quantity,b.metadata)])["ok"]

def test_missing_drawing_scale_fails_closed():
    src=DrawingSource(__file__,"pdf",{})
    adapted=AdapterResult(src,(DrawingPrimitive("line",x=0,y=0,x2=10,y2=0,source_id="L1"),))
    scale,_,warnings=DrawingMeasurementGate().apply(adapted)
    assert scale is None
    assert warnings

def test_bim_bbox_is_not_quantity_geometry():
    e=BIMElement("G1","IFCBEAM",geometry={"bbox_length":5,"bbox_width":.2})
    assert e.has_quantity_geometry is True
    assert e.has_explicit_quantity_geometry is False

def test_boq_summary_excludes_cancelled_amounts():
    rows=build_boq([
        {"item_code":"A","description":"a","quantity":1,"unit":"m3","unit_price":10,"status":"active"},
        {"item_code":"B","description":"b","quantity":1,"unit":"m3","unit_price":20,"status":"cancelled"},
    ])
    s=boq_summary(rows)
    assert s["grand_total"]==pytest.approx(10)
