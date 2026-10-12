from core.drawings.auto_takeoff import detect_scale, generate_auto_takeoff, generate_multi_sheet_takeoff
from core.drawings.dwg_takeoff import DWGEntity


def test_detect_scale_unknown_and_ambiguous_never_guess():
    assert detect_scale("drawing without scale")["status"] == "unknown"
    result = detect_scale("Scale 1:50 / detail 1:100")
    assert result["status"] == "ambiguous"
    assert result["scale"] is None
    assert result["needs_confirmation"] is True


def test_detect_scale_single_value():
    result = detect_scale("SCALE 1:100")
    assert result == {
        "status": "detected",
        "scale": 100.0,
        "candidates": [100.0],
        "needs_confirmation": False,
    }


def test_auto_takeoff_generates_length_area_and_count_candidates():
    entities = [
        DWGEntity("LINE", "WALL", "1", {"length": 4}),
        DWGEntity("LWPOLYLINE", "SLAB", "2", {"area": 20}),
        DWGEntity("INSERT", "DOOR", "3", {"block": "D1"}),
    ]
    result = generate_auto_takeoff(
        entities, scale_text="1:100", source_unit="m", sheet="A-101", page=1
    )
    assert result["summary"]["candidate_count"] == 3
    assert {x["metric"] for x in result["candidates"]} == {"length", "area", "count"}
    assert all(x["sheet"] == "A-101" and x["page"] == 1 for x in result["candidates"])


def test_unknown_scale_marks_candidates_for_review_without_changing_quantity():
    entities = [DWGEntity("LINE", "WALL", "1", {"length": 4})]
    result = generate_auto_takeoff(entities, scale_text="", source_unit="m")
    row = result["candidates"][0]
    assert row["quantity"] == 4
    assert row["scale"] is None
    assert row["needs_confirmation"] is True


def test_multi_sheet_never_reuses_scale_between_sheets():
    entities = [DWGEntity("LINE", "WALL", "1", {"length": 4})]
    result = generate_multi_sheet_takeoff({
        "A-101": {"entities": entities, "scale_text": "1:100", "page": 1},
        "A-201": {"entities": entities, "scale_text": "1:50", "page": 2},
    })
    assert result["sheets"]["A-101"]["scale"]["scale"] == 100
    assert result["sheets"]["A-201"]["scale"]["scale"] == 50
    assert result["summary"]["sheet_count"] == 2
