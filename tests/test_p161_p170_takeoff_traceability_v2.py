from core.drawing.models import DrawingPrimitive, EngineeringElement
from core.drawing.takeoff_traceability_v2 import TakeoffTraceabilityV2

def element(eid="DRAW-1", source="s1", confidence=.95):
    return EngineeringElement(eid,"structural","member",(source,),{"x":0.0,"y":0.0},confidence,("explicit",),{})

def test_p161_normalization_accepts_only_explicit_complete_candidate():
    e=element()
    c=TakeoffTraceabilityV2().normalize(e,{"quantity":12.5,"unit":"m","formula":"L","confidence":.95})
    assert c.status=="accepted" and c.quantity==12.5 and c.source_ids==("s1",)

def test_p162_missing_quantity_fails_closed():
    c=TakeoffTraceabilityV2().normalize(element(),{"unit":"m","confidence":.95})
    assert c.status=="rejected" and "مقدار متره صریح" in c.warnings[0]

def test_p163_low_confidence_requires_review():
    c=TakeoffTraceabilityV2().normalize(element(confidence=.6),{"quantity":2,"unit":"m","confidence":.6})
    assert c.status=="review"

def test_p164_invalid_negative_quantity_rejected():
    c=TakeoffTraceabilityV2().normalize(element(),{"quantity":-1,"unit":"m","confidence":.95})
    assert c.status=="rejected"

def test_p165_coverage_detects_missing_quantity_lineage():
    e=element()
    q=TakeoffTraceabilityV2().normalize(e,{"quantity":2,"unit":"m","confidence":.95})
    cov=TakeoffTraceabilityV2().coverage(["s1","s2"],[e],[q])
    assert cov[0].status=="covered" and cov[1].status=="uncovered"

def test_p166_source_without_quantity_is_review():
    e=element()
    cov=TakeoffTraceabilityV2().coverage(["s1"],[e],[])
    assert cov[0].status=="review"

def test_p167_unresolved_is_deterministic():
    e=element()
    a=TakeoffTraceabilityV2().normalize(e,{"quantity":1,"unit":"m","confidence":.4})
    assert TakeoffTraceabilityV2.unresolved([a])==(a,)

def test_p168_order_is_stable():
    e1=element("DRAW-2","s2"); e2=element("DRAW-1","s1")
    w=TakeoffTraceabilityV2()
    cs=[w.normalize(e1,{"quantity":2,"unit":"m"}),w.normalize(e2,{"quantity":1,"unit":"m"})]
    assert [c.element_id for c in w.deterministic_order(cs)]==["DRAW-1","DRAW-2"]

def test_p169_fingerprint_changes_with_quantity():
    e=element(); w=TakeoffTraceabilityV2()
    a=w.normalize(e,{"quantity":1,"unit":"m"}); b=w.normalize(e,{"quantity":2,"unit":"m"})
    assert a.fingerprint != b.fingerprint

def test_p170_no_source_cannot_be_accepted():
    e=EngineeringElement("DRAW-X","structural","member",(),{"x":0.0,"y":0.0},.99,("explicit",),{})
    c=TakeoffTraceabilityV2().normalize(e,{"quantity":1,"unit":"m","confidence":.99})
    assert c.status=="rejected"
