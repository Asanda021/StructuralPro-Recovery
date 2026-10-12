from core.drawing.models import DrawingPrimitive
from core.drawing.intelligence_v2 import DrawingIntelligenceV2

def test_p141_sheet_scale_recognition_and_links():
    ps=(DrawingPrimitive("text",text="A-101",source_id="s1",properties={"page":1}),DrawingPrimitive("text",text="1:100",source_id="s2",properties={"page":1}),DrawingPrimitive("text",text="B1",source_id="s3",layer="BEAM",properties={"page":1}),DrawingPrimitive("line",x=0,y=0,x2=5,y2=0,source_id="g1",properties={"page":1}))
    d=DrawingIntelligenceV2()
    sheets=d.detect_sheets(ps)
    assert sheets[0].sheet_id=="A-101"
    assert d.infer_scale(ps).denominator==100
    assert any(x.action=="accept" for x in d.recognize(ps))
    assert d.link_semantics(ps,sheets)[0].key=="1"

def test_p141_duplicate_suppression_is_deterministic():
    p=DrawingPrimitive("line",x=1,y=2,x2=3,y2=4,source_id="a")
    assert len(DrawingIntelligenceV2().suppress_duplicates((p,p)))==1

def test_p141_missing_identity_fails_closed():
    p=DrawingPrimitive("line")
    assert DrawingIntelligenceV2().recognize((p,))[0].action=="reject"

def test_p141_low_confidence_goes_to_review():
    p=DrawingPrimitive("arc",source_id="a")
    assert DrawingIntelligenceV2().recognize((p,))[0].action=="review"
