from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession


def test_priority_13_calibration_measurement_and_boq_link():
    s = DrawingTakeoffSession("plans/A-101.pdf")
    s.set_page(2)
    cal = s.calibrate(2, 1000, 10)
    assert cal.meters_per_pixel == 0.01

    item = s.add_length(
        [Point(0, 0), Point(1000, 0)],
        label="دیوار خارجی",
        takeoff_code="W001",
        source="pdf:A-101:p2:wall-1",
    )
    assert item.quantity == 10
    assert item.source_ref.endswith("page=2&takeoff=TO-00001")

    row = s.boq_rows()[0]
    assert row["quantity"] == 10
    assert row["unit"] == "m"
    assert row["price_code"] == "W001"
    assert row["source_id"] == row["source"]


def test_priority_13_area_count_and_validation():
    s = DrawingTakeoffSession("plan.pdf")
    s.calibrate(1, 1000, 10)
    area = s.add_area(
        [Point(0, 0), Point(1000, 0), Point(1000, 500), Point(0, 500)],
        label="کف",
        source="pdf:plan:p1:floor",
    )
    count = s.add_count(4, label="در", source="pdf:plan:p1:doors")
    assert area.quantity == 50
    assert count.quantity == 4
    assert s.validate()["valid"] is True


def test_priority_13_duplicate_source_is_blocked():
    s = DrawingTakeoffSession("plan.pdf")
    s.calibrate(1, 100, 1)
    s.add_count(1, source="same")
    try:
        s.add_count(1, source="same")
        assert False, "duplicate source must be rejected"
    except ValueError as exc:
        assert "دوباره" in str(exc)


def test_priority_13_undo_redo_and_edit():
    s = DrawingTakeoffSession("plan.pdf")
    s.calibrate(1, 100, 1)
    item = s.add_count(2, label="ستون", source="cad:column:1")
    assert s.can_undo is True
    assert s.edit(item.id, quantity=3).quantity == 3
    assert s.undo() is True
    assert s.find(item.id).quantity == 2
    assert s.redo() is True
    assert s.find(item.id).quantity == 3
    assert s.remove(item.id) is True
    assert s.for_page(1) == []


def test_priority_13_serialization_roundtrip_and_markup():
    s = DrawingTakeoffSession("plan.pdf")
    s.calibrate(1, 100, 1)
    s.add_note("کنترل ابعاد", 20, 30)
    s.add_length([Point(0, 0), Point(100, 0)], label="خط مبنا")
    restored = DrawingTakeoffSession.from_dict(s.to_dict())
    assert len(restored.items) == 1
    assert restored.items[0].quantity == 1
    assert len(restored.markups.items) == 1
    assert restored.markups.items[0].text == "کنترل ابعاد"


def test_priority_13_graphical_session_maps_to_boq_workflow():
    from core.takeoff.workflow import TakeoffWorkflow
    s = DrawingTakeoffSession("A-101.pdf")
    s.calibrate(1, 100, 1)
    s.add_length([Point(0, 0), Point(100, 0)], label="دیوار", takeoff_code="W001")
    rows = TakeoffWorkflow().graphical_rows(s)
    assert len(rows) == 1
    assert rows[0]["description"] == "دیوار"
    assert rows[0]["price_code"] == "W001"
    assert rows[0]["source_id"].startswith("A-101.pdf#page=1")
