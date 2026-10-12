from core.drawings.dwg_takeoff import DWGEntity
from core.drawings.element_recognition import recognize_entity
from core.drawings.geometry_takeoff import aggregate_geometry_candidates, extract_geometry_candidates


def test_recognition_prefers_block_over_layer_and_text():
    entity = DWGEntity(
        "INSERT", "A-WALL", "1", {"block": "COL-400", "text": "door"}
    )
    result = recognize_entity(entity)
    assert result.element_type == "column"
    assert result.confidence > 0.8
    assert "block:" in result.reason
    assert result.needs_confirmation is True


def test_recognition_marks_conflicting_equal_signals_unknown():
    entity = DWGEntity("LINE", "BEAM-WALL", "2", {"text": "column"})
    result = recognize_entity(entity)
    assert result.element_type == "unknown"
    assert result.needs_confirmation is True


def test_recognition_unknown_is_safe():
    entity = DWGEntity("LINE", "A-GRID", "3", {"length": 5})
    result = recognize_entity(entity)
    assert result.element_type == "unknown"
    assert result.confidence == 0.0


def test_geometry_candidates_keep_recognition_without_changing_quantity():
    entity = DWGEntity("LINE", "S-COL", "A1", {"length": 4})
    row = extract_geometry_candidates([entity])[0]
    assert row["quantity"] == 4
    assert row["element_type"] == "column"
    assert row["needs_confirmation"] is True


def test_aggregation_separates_semantic_types_on_same_layer():
    entities = [
        DWGEntity("LINE", "STRUCT", "B1", {"length": 4}),
        DWGEntity("LINE", "STRUCT", "W1", {"length": 6}),
    ]
    # Explicit block/text signals are used through the same layer by supplying
    # semantic text fields on the entities.
    entities[0] = DWGEntity("LINE", "STRUCT", "B1", {"length": 4, "text": "beam"})
    entities[1] = DWGEntity("LINE", "STRUCT", "W1", {"length": 6, "text": "wall"})
    rows = aggregate_geometry_candidates(entities)
    assert {(r["element_type"], r["quantity"]) for r in rows} == {
        ("beam", 4), ("wall", 6)
    }
