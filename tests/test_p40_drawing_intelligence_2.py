from core.drawing.intelligence_v3 import inspect_source, normalize_ocr, classify_sheets, cross_sheet_relations
from core.drawing.models import DrawingPrimitive

def test_source_formats_are_classified():
    assert inspect_source("plan.pdf").format=="pdf"
    assert inspect_source("model.dwg").format=="dwg"

def test_ocr_is_normalized_without_inventing_text():
    assert normalize_ocr("  ستون   C1  ").text=="ستون C1"

def test_sheet_and_cross_sheet_semantics():
    p=(DrawingPrimitive("text",text="S-01",source_id="a",properties={"page":1}),
       DrawingPrimitive("text",text="B-01",source_id="b",properties={"page":2}))
    sheets=classify_sheets(p)
    assert sheets
    rel=cross_sheet_relations(p,sheets)
    assert rel
