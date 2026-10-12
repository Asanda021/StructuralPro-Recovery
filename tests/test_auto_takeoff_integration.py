from core.drawings.auto_takeoff import generate_auto_takeoff
from core.drawings.dwg_takeoff import DWGEntity


def test_explicit_opening_exposes_net_quantity_without_mutating_gross():
    entities = [DWGEntity("LWPOLYLINE", "SLAB", "1", {"area": 20})]
    result = generate_auto_takeoff(
        entities,
        scale_text="1:100",
        source_unit="m",
        openings=[{"parent_source": "cad:SLAB:1", "quantity": 3}],
    )
    row = result["candidates"][0]
    assert row["quantity"] == 20
    assert row["opening_quantity"] == 3
    assert row["net_quantity"] == 17
    assert row["needs_confirmation"] is True


def test_excessive_opening_is_review_flag_not_negative_quantity():
    entities = [DWGEntity("LWPOLYLINE", "SLAB", "1", {"area": 20})]
    result = generate_auto_takeoff(
        entities,
        scale_text="1:100",
        source_unit="m",
        openings=[{"parent_source": "cad:SLAB:1", "quantity": 25}],
    )
    row = result["candidates"][0]
    assert row["quantity"] == 20
    assert row["net_quantity"] == 0
    assert row["opening_exceeds_gross"] is True
    assert row["opening_error"] is True
    assert row["needs_confirmation"] is True
