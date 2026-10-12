from core.drawings.dwg_takeoff import DWGEntity
from core.drawings.geometry_takeoff import extract_geometry_candidates, aggregate_geometry_candidates


def test_exact_duplicate_line_geometry_is_flagged_even_with_different_handles():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (5, 0), "length": 5}),
        DWGEntity("LINE", "WALL", "B9", {"start": (0, 0), "end": (5, 0), "length": 5}),
    ]
    rows = extract_geometry_candidates(entities)
    assert rows[0]["duplicate_geometry"] is False
    assert rows[1]["duplicate_geometry"] is True
    assert rows[1]["duplicate_of"] == rows[0]["source"]
    assert rows[1]["needs_confirmation"] is True


def test_duplicate_geometry_is_exposed_at_aggregate_level():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (5, 0), "length": 5}),
        DWGEntity("LINE", "WALL", "B9", {"start": (0, 0), "end": (5, 0), "length": 5}),
    ]
    rows = aggregate_geometry_candidates(entities)
    assert rows[0]["quantity"] == 10
    assert rows[0]["entity_count"] == 2
    assert rows[0]["duplicate_geometry_count"] == 1
    assert rows[0]["needs_confirmation"] is True
    assert rows[0]["duplicate_sources"][0]["duplicate_of"] == "cad:WALL:A1"


def test_different_lines_are_not_marked_as_duplicates():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (5, 0), "length": 5}),
        DWGEntity("LINE", "WALL", "B9", {"start": (0, 1), "end": (5, 1), "length": 5}),
    ]
    rows = extract_geometry_candidates(entities)
    assert all(not row["duplicate_geometry"] for row in rows)


def test_reverse_direction_of_same_line_is_flagged_as_duplicate():
    entities = [
        DWGEntity("LINE", "WALL", "A1", {"start": (0, 0), "end": (5, 0), "length": 5}),
        DWGEntity("LINE", "WALL", "B9", {"start": (5, 0), "end": (0, 0), "length": 5}),
    ]
    rows = extract_geometry_candidates(entities)

    assert rows[0]["duplicate_geometry"] is False
    assert rows[1]["duplicate_geometry"] is True
    assert rows[1]["duplicate_of"] == rows[0]["source"]
    assert rows[1]["needs_confirmation"] is True
