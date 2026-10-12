import math
import pytest

from core.drawings.graphical_takeoff import MeasurementStore, Point, ScaleCalibration, polygon_area, polyline_length, subtract_areas, snap_point


@pytest.mark.parametrize("ratio", [0, -1, math.nan, math.inf, -math.inf, True])
def test_scale_calibration_rejects_invalid_ratios(ratio):
    with pytest.raises(ValueError):
        ScaleCalibration.parse(ratio)


@pytest.mark.parametrize("distance", [-1, math.nan, math.inf, -math.inf])
def test_scale_calibration_rejects_invalid_lengths(distance):
    with pytest.raises(ValueError):
        ScaleCalibration.parse(100).length(distance)


@pytest.mark.parametrize("area", [-1, math.nan, math.inf, -math.inf])
def test_scale_calibration_rejects_invalid_areas(area):
    with pytest.raises(ValueError):
        ScaleCalibration.parse(100).area(area)


@pytest.mark.parametrize("points", [
    [Point(0, 0), Point(math.nan, 1)],
    [Point(0, 0), Point(math.inf, 1)],
])
def test_polyline_rejects_non_finite_coordinates(points):
    with pytest.raises(ValueError):
        polyline_length(points)


def test_polygon_area_rejects_non_finite_coordinates():
    with pytest.raises(ValueError):
        polygon_area([Point(0, 0), Point(1, 0), Point(math.nan, 1)])


@pytest.mark.parametrize("holes", [[-1], [math.nan], [math.inf]])
def test_area_subtraction_rejects_invalid_openings(holes):
    with pytest.raises(ValueError):
        subtract_areas(10, holes)


def test_snap_rejects_negative_or_non_finite_tolerance():
    for tolerance in (-1, math.nan, math.inf):
        with pytest.raises(ValueError):
            snap_point(Point(0, 0), [Point(1, 1)], tolerance)


def test_invalid_measurement_does_not_mutate_store_or_consume_id():
    store = MeasurementStore()
    scale = ScaleCalibration.parse(100)
    with pytest.raises(ValueError):
        store.add_length([Point(0, 0), Point(math.nan, 0)], scale)
    assert store.all() == []
    valid = store.add_length([Point(0, 0), Point(1, 0)], scale)
    assert valid.id == "M00001"

from core.takeoff.manual_input import parse_manual_entry
from core.takeoff.manual_workbench import ManualTakeoffWorkbench


@pytest.mark.parametrize("entry", [
    "ستون: تعداد=-2، عرض=0.5، عمق=0.5، ارتفاع=3",
    "ستون: تعداد=2، عرض=-0.5، عمق=0.5، ارتفاع=3",
    "ستون: تعداد=2، عرض=0.5، عمق=0.5، ارتفاع=-3",
    "-2 ستون 50x50 ارتفاع 3",
])
def test_manual_takeoff_rejects_negative_values_instead_of_reading_absolute_value(entry):
    with pytest.raises(ValueError, match="منفی"):
        parse_manual_entry(entry)


def test_manual_workbench_does_not_save_invalid_negative_manual_entry():
    workbench = ManualTakeoffWorkbench("project-phase-2")
    with pytest.raises(ValueError):
        workbench.add_text(
            "ستون: تعداد=2، عرض=-0.5، عمق=0.5، ارتفاع=3",
            floor_id="level-1",
        )
    assert workbench.records == ()


def test_area_and_count_failures_do_not_mutate_measurement_store():
    store = MeasurementStore()
    scale = ScaleCalibration.parse(100)
    with pytest.raises(ValueError):
        store.add_area([Point(0, 0), Point(1, 0)], scale)
    with pytest.raises(ValueError):
        store.add_count(1.5)
    assert store.all() == []
    valid = store.add_count(2)
    assert valid.id == "M00001"

def test_viewer_failed_open_preserves_the_previously_open_drawing(tmp_path):
    fitz = pytest.importorskip("fitz")
    from core.drawings.viewer_model import DrawingViewerModel

    path = tmp_path / "valid.pdf"
    document = fitz.open()
    document.new_page(width=100, height=100)
    document.save(path)
    document.close()

    viewer = DrawingViewerModel(path)
    before = (viewer.path, viewer.kind, viewer.page_count, viewer.current_page)
    unsupported = tmp_path / "unsupported.txt"
    unsupported.write_text("not a drawing", encoding="utf-8")
    with pytest.raises(ValueError):
        viewer.open(unsupported)
    assert (viewer.path, viewer.kind, viewer.page_count, viewer.current_page) == before


def test_snap_with_empty_candidate_iterator_is_a_noop():
    point = Point(2, 3)
    assert snap_point(point, iter(()), 1) == point


def test_scale_calibration_converts_between_drawing_and_model_units():
    scale_cm = ScaleCalibration.parse("1:100", drawing_unit="cm", model_unit="cm")
    assert scale_cm.length(1) == pytest.approx(100)
    assert scale_cm.area(1) == pytest.approx(10000)

    scale_mm_to_m = ScaleCalibration.parse(100, drawing_unit="mm", model_unit="m")
    assert scale_mm_to_m.length(100) == pytest.approx(10)
    assert scale_mm_to_m.area(10000) == pytest.approx(100)


def test_measurement_store_uses_the_calibrated_model_unit():
    store = MeasurementStore()
    scale = ScaleCalibration.parse(100, drawing_unit="cm", model_unit="cm")
    line = store.add_length([Point(0, 0), Point(1, 0)], scale)
    area = store.add_area([Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)], scale)
    assert line.unit == "cm"
    assert line.value == pytest.approx(100)
    assert area.unit == "cm2"
    assert area.value == pytest.approx(10000)
