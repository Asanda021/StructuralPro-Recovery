from core.drawings.dwg_takeoff import DWGEntity
from core.drawings.geometry_takeoff import aggregate_geometry_candidates, extract_geometry_candidates


def test_partial_collinear_overlap_is_flagged_without_changing_quantities():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (10, 0), "length": 10}),
        DWGEntity("LINE", "WALL", "A2", {"start": (5, 0), "end": (15, 0), "length": 10}),
    ]

    rows = extract_geometry_candidates(entities)

    assert rows[0]["partial_overlap"] is False
    assert rows[1]["partial_overlap"] is True
    assert rows[1]["overlap_sources"][0]["source"] == "cad:WALL:A1"
    assert rows[1]["overlap_length"] == 5
    assert rows[0]["quantity"] == 10
    assert rows[1]["quantity"] == 10
    assert rows[1]["needs_confirmation"] is True


def test_touching_line_endpoints_are_not_partial_overlap():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (5, 0), "length": 5}),
        DWGEntity("LINE", "WALL", "A2", {"start": (5, 0), "end": (10, 0), "length": 5}),
    ]

    rows = extract_geometry_candidates(entities)

    assert not rows[0]["partial_overlap"]
    assert not rows[1]["partial_overlap"]


def test_parallel_non_collinear_lines_are_not_partial_overlap():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (10, 0), "length": 10}),
        DWGEntity("LINE", "WALL", "A2", {"start": (5, 1), "end": (15, 1), "length": 10}),
    ]

    rows = extract_geometry_candidates(entities)

    assert not rows[1]["partial_overlap"]


def test_aggregate_exposes_partial_overlap_for_review():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (10, 0), "length": 10}),
        DWGEntity("LINE", "WALL", "A2", {"start": (5, 0), "end": (15, 0), "length": 10}),
    ]

    rows = aggregate_geometry_candidates(entities)

    assert rows[0]["quantity"] == 20
    assert rows[0]["partial_overlap_count"] == 1
    assert rows[0]["overlap_length"] == 5
    assert rows[0]["needs_confirmation"] is True
