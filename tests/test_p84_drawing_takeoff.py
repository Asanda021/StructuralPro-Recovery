import pytest
from core.drawing.models import DrawingPrimitive, EngineeringElement
from core.drawing.review import DrawingTakeoffSelection, recognize_text, review_queue

def test_dimension_level_and_grid_recognition_are_explicit():
    ps=(
      DrawingPrimitive("text",text="6000 mm",source_id="D",properties={"page":2}),
      DrawingPrimitive("text",text="Level +3.20",source_id="L",properties={"page":2}),
      DrawingPrimitive("text",text="A",source_id="G",properties={"page":2}),
    )
    kinds={x.kind for x in recognize_text(ps)}
    assert {"dimension","level","grid"} <= kinds

def test_unclassified_geometry_enters_human_review_queue():
    p=DrawingPrimitive("line",x=0,y=0,x2=10,y2=0,source_id="LINE1")
    assert review_queue((p,),()) [0].kind=="unclassified_geometry"

def test_selection_is_explicit_and_non_destructive():
    ps=(DrawingPrimitive("line",source_id="A"),DrawingPrimitive("line",source_id="B"))
    s=DrawingTakeoffSelection(["A"])
    assert [p.source_id for p in s.apply(ps)]==["A"]
    s.select("B"); s.deselect("A")
    assert [p.source_id for p in s.apply(ps)]==["B"]

def test_review_does_not_turn_unknown_geometry_into_engineering_element():
    p=DrawingPrimitive("line",source_id="UNKNOWN")
    e=EngineeringElement("E","concrete","beam",("KNOWN",),{"length":1},0.9)
    q=review_queue((p,),(e,))
    assert q and q[0].source_id=="UNKNOWN"


def test_graphical_pdf_extracts_vector_lines_and_text(tmp_path):
    fitz=pytest.importorskip("fitz")
    doc=fitz.open(); page=doc.new_page(width=200,height=200)
    page.draw_line((10,10),(110,10)); page.insert_text((20,40),"BEAM-1")
    path=tmp_path/"vector.pdf"; doc.save(str(path)); doc.close()
    from core.drawing.pdf_graphics import GraphicalPDFAdapter
    result=GraphicalPDFAdapter().read(path)
    kinds={p.normalized_kind() for p in result.primitives}
    assert "line" in kinds and "text" in kinds
    assert all(p.properties.get("page")==1 for p in result.primitives)
