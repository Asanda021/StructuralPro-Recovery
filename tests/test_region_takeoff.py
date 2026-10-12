import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.region_takeoff import calibrated_rectangle_area, rectangle_to_points
from core.drawings.takeoff_session import DrawingTakeoffSession


def test_rectangle_to_points_normalizes_reverse_drag_and_closes_polygon():
    points = rectangle_to_points(20, 30, 5, 10)
    assert points == ((5.0, 10.0), (20.0, 10.0), (20.0, 30.0), (5.0, 30.0))


@pytest.mark.parametrize("coords", [(1, 1, 1, 4), (1, 1, 4, 1), (2, 2, 2, 2)])
def test_rectangle_to_points_rejects_zero_area(coords):
    with pytest.raises(ValueError):
        rectangle_to_points(*coords)


def test_rectangle_to_points_rejects_non_finite_coordinates():
    with pytest.raises(ValueError):
        rectangle_to_points(0, 0, float("inf"), 10)


def test_selected_region_can_become_a_calibrated_traceable_boq_row():
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(page=2, reference_pixels=100, reference_meters=10)
    points = [Point(x, y) for x, y in rectangle_to_points(10, 20, 30, 60)]
    item = session.add_area(
        points, page=2, label="کف اتاق ۱۰۱", takeoff_code="A-101",
        source="region:page=2:left=10:top=20:right=30:bottom=60",
    )
    row = session.boq_rows([item.id])[0]
    assert item.quantity == pytest.approx(8.0)
    assert row["takeoff_id"] == item.id
    assert row["page"] == 2
    assert row["price_code"] == "A-101"
    assert row["source"].startswith("plan.pdf#page=2&takeoff=")
    assert row["needs_confirmation"] is False


def test_registering_same_region_twice_is_rejected_to_prevent_double_counting():
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(page=1, reference_pixels=100, reference_meters=1)
    points = [Point(x, y) for x, y in rectangle_to_points(0, 0, 10, 10)]
    kwargs = dict(page=1, label="ناحیه", source="region:page=1:rect=0,0,10,10")
    session.add_area(points, **kwargs)
    with pytest.raises(ValueError, match="دوباره‌شماری"):
        session.add_area(points, **kwargs)


def test_calibrated_rectangle_area_previews_quantity_without_creating_an_item():
    session = DrawingTakeoffSession("plan.pdf")
    session.set_page(2)
    session.calibrate(page=2, reference_pixels=100, reference_meters=10)
    area = calibrated_rectangle_area(10, 20, 30, 60, session.calibration.meters_per_pixel)
    assert area == pytest.approx(8.0)
    assert session.items == []


@pytest.mark.parametrize("factor", [0, -0.1, float("inf"), float("nan")])
def test_calibrated_rectangle_area_rejects_invalid_calibration(factor):
    with pytest.raises(ValueError):
        calibrated_rectangle_area(0, 0, 10, 10, factor)


def test_calibrated_rectangle_area_rejects_invalid_region():
    with pytest.raises(ValueError):
        calibrated_rectangle_area(0, 0, 0, 10, 0.1)
