from core.drawing.models import DrawingPrimitive
from core.drawing.intelligence_v2 import DrawingIntelligenceV2
from core.drawing.production_v1 import Correction, DrawingProductionWorkflow

def test_p151_dimensions_are_explicit_and_fail_closed():
    ps=(DrawingPrimitive("text",text="DIM: 6000 mm",source_id="d1"),DrawingPrimitive("text",text="unknown",source_id="d2"))
    got=DrawingProductionWorkflow().extract_dimensions(ps)
    assert got[0].value==6000 and got[0].unit=="mm" and len(got)==1

def test_p151_axis_and_zone_link_to_sheet():
    ps=(DrawingPrimitive("text",text="A-101",source_id="s1",properties={"page":1}),DrawingPrimitive("text",text="AXIS A",source_id="a1",properties={"page":1}),DrawingPrimitive("text",text="ROOM R01",source_id="r1",properties={"page":1}))
    d=DrawingIntelligenceV2(); sheets=d.detect_sheets(ps); w=DrawingProductionWorkflow()
    assert w.infer_axes(ps,sheets)[0].sheet_ids==("A-101",)
    assert w.infer_zones(ps,sheets)[0].sheet_ids==("A-101",)

def test_p151_elements_are_provenance_bound():
    p=DrawingPrimitive("text",text="B1",source_id="m1",layer="BEAM")
    e=DrawingProductionWorkflow().recognize_elements((p,))[0]
    assert e.element_id=="DRAW-m1" and e.source_ids==("m1",) and e.confidence>=.9

def test_p151_reconciliation_is_deterministic():
    p=DrawingPrimitive("text",text="B1",source_id="m1",layer="BEAM")
    e=DrawingProductionWorkflow().recognize_elements((p,))[0]
    assert DrawingProductionWorkflow().reconcile_sources((e,))=={"m1":("DRAW-m1",)}

def test_p151_human_correction_is_explicit():
    c=DrawingProductionWorkflow().apply_correction(Correction("m1","label","B1","B2"))
    assert c.actor=="human"

def test_p151_invalid_correction_fails_closed():
    try: DrawingProductionWorkflow().apply_correction(Correction("m1","secret","x","y"))
    except ValueError: return
    assert False

def test_p151_prior_generation_remains_compatible():
    p=DrawingPrimitive("text",text="B1",source_id="m1",layer="BEAM")
    assert DrawingIntelligenceV2().recognize((p,))[0].action=="accept"
