from core.drawings.dwg_takeoff import DWGDocument, DWGEntity, infer_takeoff_from_layers
from core.drawings.bim_quantities import classify_objects, extract_quantities, link_2d_3d
from core.drawings.pdf_takeoff import PDFPageInfo, PDFTakeoffAdapter
import pytest


def test_dwg_layer_quantity():
    doc = DWGDocument([
        DWGEntity("LINE", "WALL", "1", {"length": 4}),
        DWGEntity("LINE", "WALL", "2", {"length": 6}),
    ], ["WALL"], units="m")
    rows = infer_takeoff_from_layers(
        doc, {"WALL": {"description": "wall", "unit": "m", "metric": "length", "price_code": "W1"}}
    )
    assert rows[0]["quantity"] == 10
    assert rows[0]["count"] == 2
    assert rows[0]["needs_confirmation"] is True


def test_dwg_missing_metric_uses_count():
    doc = DWGDocument([
        DWGEntity("INSERT", "DOOR", "1", {"block": "D1"}),
        DWGEntity("INSERT", "DOOR", "2", {"block": "D1"}),
        DWGEntity("INSERT", "DOOR", "3", {"block": "D2"}),
    ], ["DOOR"])
    rows = infer_takeoff_from_layers(doc, {"DOOR": {"description": "doors", "unit": "count"}})
    assert rows[0]["quantity"] == 3
    assert rows[0]["count"] == 3


def test_pdf_scale_measurement():
    p = PDFTakeoffAdapter()
    assert p.normalize_scale("1:100") == 100
    assert p.normalize_scale("1 / 50") == 50
    assert p.pixel_to_model(2, "1:100", "cm") == 2
    assert round(p.measure_area(0.01, "1:100").value, 2) == 100


def test_pdf_line_measurement():
    p = PDFTakeoffAdapter()
    m = p.measure_line(0, 0, 1, 0, "1:100", "cm")
    assert m.kind == "length"
    assert m.unit == "m"
    assert m.value == 1


def test_pdf_text_candidates_and_confirmation():
    p = PDFTakeoffAdapter()
    pages = [PDFPageInfo(1, 100, 100, "Wall 250 cm\nSlab 3 m")]
    rows = p.text_takeoff_candidates(pages)
    assert len(rows) == 2
    assert rows[0]["needs_confirmation"] is True
    assert rows[0]["unit"] == "m"


def test_bim_link_and_quantities():
    class O:
        ifc_type = "IfcWall"
        global_id = "G1"
        name = "Wall"
        properties = {"Length": 5, "Area": 12, "Bad": "x"}

    rows = extract_quantities([O()])
    assert rows[0]["quantities"]["Length"] == 5
    assert rows[0]["quantities"]["Area"] == 12
    assert "Bad" not in rows[0]["quantities"]
    assert classify_objects([O()])["IfcWall"] == 1
    linked = link_2d_3d([{"global_id": "G1"}, {"global_id": "G2"}], rows)
    assert linked[0]["linked"] is True
    assert linked[1]["linked"] is False


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), "invalid", True])
def test_bim_quantity_adapter_rejects_invalid_values(value):
    class O:
        ifc_type = "IfcWall"
        global_id = "G1"
        name = "Wall"
        properties = {"Length": value}

    with pytest.raises(ValueError, match="کمیت IFC"):
        extract_quantities([O()])


def test_bim_quantity_adapter_rejects_duplicate_identity_at_extract_and_link():
    class O:
        ifc_type = "IfcWall"
        global_id = "G1"
        name = "Wall"
        properties = {"Length": 5}

    with pytest.raises(ValueError, match="GlobalId تکراری"):
        extract_quantities([O(), O()])
    duplicate_rows = [
        {"global_id": "G1", "quantities": {"Length": 5}},
        {"global_id": "G1", "quantities": {"Length": 6}},
    ]
    with pytest.raises(ValueError, match="GlobalId تکراری"):
        link_2d_3d([], duplicate_rows)

from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
from core.takeoff.drawing_pipeline import DrawingTakeoffPipeline

def test_unified_confirmed_rows_reject_duplicate_sources():
    u = UnifiedDrawingTakeoff()
    with pytest.raises(ValueError, match="دوباره"):
        u.candidates_to_rows({"candidates":[
            {"source":"PDF:p1:L1","description":"wall","quantity":10,"unit":"m"},
            {"source":"PDF:p1:L1","description":"wall duplicate","quantity":5,"unit":"m"},
        ]})

def test_drawing_pipeline_normalizes_units_and_rejects_invalid_data():
    p = DrawingTakeoffPipeline()
    rows = p.normalize([
        {"source":"dwg:WALL:1","description":"wall","quantity":100,"unit":"cm","unit_price":10},
        {"source":"dwg:WALL:2","description":"wall","quantity":2,"unit":"m","unit_price":10},
    ])
    assert rows[0].unit == "cm"
    assert rows[0].total == 1000
    with pytest.raises(ValueError, match="دوباره"):
        p.normalize([
            {"source":"dwg:X","description":"x","quantity":1,"unit":"m"},
            {"source":"dwg:X","description":"x","quantity":2,"unit":"m"},
        ])
    with pytest.raises(ValueError):
        p.normalize([{"source":"dwg:bad","description":"x","quantity":-1,"unit":"m"}])

def test_ifc_duplicate_global_id_fails_closed():
    from core.drawings.ifc_pipeline import normalize_ifc_rows
    with pytest.raises(ValueError, match="GlobalId تکراری"):
        normalize_ifc_rows([
            {"global_id":"G1","ifc_type":"IfcWall","quantities":{"Length":5}},
            {"global_id":"G1","ifc_type":"IfcWall","quantities":{"Length":6}},
        ])

def test_dwg_metric_rejects_nonfinite_and_preserves_units():
    from core.drawings.dwg_takeoff import DWGTakeoffEngine
    doc = DWGDocument([DWGEntity("LINE", "WALL", "1", {"length": 4})], ["WALL"], units="m")
    rows = DWGTakeoffEngine().layer_takeoff(doc, {"WALL": {"metric": "length", "unit": "m"}})
    assert rows[0]["source"] == "dwg-layer:WALL"
    import math
    bad = DWGDocument([DWGEntity("LINE", "WALL", "1", {"length": math.nan})], ["WALL"])
    with pytest.raises(ValueError):
        DWGTakeoffEngine().layer_takeoff(bad, {"WALL": {"metric": "length", "unit": "m"}})


@pytest.mark.parametrize("name,value", [("Volume", -1), ("Volume", float("nan")), ("Bad", 1)])
def test_ifc_quantities_fail_closed_for_invalid_value_or_unknown_unit(name, value):
    from core.drawings.ifc_pipeline import normalize_ifc_rows
    with pytest.raises(ValueError, match="کمیت IFC"):
        normalize_ifc_rows([{"global_id":"G1","ifc_type":"IfcWall","quantities":{name:value}}])


def test_ifc_multi_quantity_rows_have_unique_sources():
    from core.drawings.ifc_pipeline import normalize_ifc_rows, map_ifc_to_boq
    rows = normalize_ifc_rows([{"global_id":"G1","ifc_type":"IfcWall","quantities":{"Length":5,"Area":12}}])
    assert set(rows[0]["quantities"]) == {"Length","Area"}
    mapped = map_ifc_to_boq(rows, {"IfcWall":"W1"})
    assert {r["source"] for r in mapped["rows"]} == {"ifc:G1:Length","ifc:G1:Area"}


def test_unified_ifc_multi_quantity_candidates_do_not_trigger_duplicate_source_guard():
    from core.drawings.unified_takeoff import UnifiedDrawingTakeoff
    u = UnifiedDrawingTakeoff()
    inspection = {"candidates":[
        {"source":"ifc:G1:Length","description":"wall Length","quantity":5,"unit":"m"},
        {"source":"ifc:G1:Area","description":"wall Area","quantity":12,"unit":"m2"},
    ]}
    assert len(u.candidates_to_rows(inspection)) == 2


def test_unified_requires_explicit_confirmation_for_review_required_candidates():
    u = UnifiedDrawingTakeoff()
    inspection = {"candidates":[
        {"source":"pdf:1:wall","description":"wall","quantity":10,"unit":"m","needs_confirmation":True},
        {"source":"dwg:1","description":"beam","quantity":5,"unit":"m","needs_confirmation":False},
    ]}
    assert [r["source"] for r in u.candidates_to_rows(inspection)] == ["dwg:1"]
    assert [r["source"] for r in u.candidates_to_rows(inspection, {1: True})] == ["pdf:1:wall", "dwg:1"]


def test_unified_confirmation_can_explicitly_reject_safe_candidate():
    u = UnifiedDrawingTakeoff()
    inspection = {"candidates":[
        {"source":"dwg:1","description":"beam","quantity":5,"unit":"m","needs_confirmation":False},
    ]}
    assert u.candidates_to_rows(inspection, {1: False}) == []


