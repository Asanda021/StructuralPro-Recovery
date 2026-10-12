from core.drawing import DrawingIntelligence, DrawingPrimitive, drawing_takeoff

def test_layer_classification_is_deterministic_and_auditable():
    items=[
        DrawingPrimitive("line",x=0,y=0,x2=5,y2=0,layer="BEAM",source_id="L1"),
        DrawingPrimitive("text",x=1,y=1,text="COL-2",source_id="T1"),
        DrawingPrimitive("rect",x=0,y=0,width=2,height=3,layer="WALL",source_id="R1"),
    ]
    elements=DrawingIntelligence().classify(items)
    assert [e.kind for e in elements] == ["beam","column","wall"]
    assert elements[0].geometry["length"] == 5
    assert elements[0].confidence == 0.95
    assert elements[0].source_ids == ("L1",)

def test_text_classification_supports_engineering_labels():
    items=[DrawingPrimitive("text",text="BEAM-12"),DrawingPrimitive("text",text="FOOTING-3")]
    elements=DrawingIntelligence().classify(items)
    assert [(e.domain,e.kind) for e in elements] == [
        ("concrete","beam"),("foundations","isolated")
    ]

def test_unknown_primitives_are_not_invented():
    elements=DrawingIntelligence().classify([DrawingPrimitive("line",x=0,y=0,x2=2,y2=0,layer="GRID")])
    assert elements == ()

def test_takeoff_preserves_traceability_and_flags_missing_dimensions():
    items=[DrawingPrimitive("line",x=0,y=0,x2=4,y2=0,layer="BEAM",source_id="B1")]
    elements=DrawingIntelligence().classify(items)
    rows=drawing_takeoff(elements)
    assert rows[0]["quantity"] == 4 and rows[0]["unit"] == "m"
    assert rows[0]["source_ids"] == ("B1",)

def test_summary_counts_classified_elements():
    items=[DrawingPrimitive("line",x=0,y=0,x2=3,y2=0,layer="BEAM"),
           DrawingPrimitive("line",x=0,y=0,x2=2,y2=0,layer="BEAM")]
    assert DrawingIntelligence().summary(items) == {"beam":2}
