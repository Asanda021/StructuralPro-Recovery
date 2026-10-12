import pytest

from core.cad.persian_text_v1 import is_rtl_cad_text, normalize_cad_text
from core.drawings.region_takeoff import calibrated_rectangle_area, rectangle_to_points
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.viewport_tools import ViewportRect
from core.drawings.viewer_model import DrawingViewerModel


def test_viewer_model_rejects_missing_or_unsupported_drawing(tmp_path):
    with pytest.raises(FileNotFoundError):
        DrawingViewerModel(tmp_path / "missing.pdf")
    unsupported = tmp_path / "drawing.png"
    unsupported.write_bytes(b"not a supported drawing")
    with pytest.raises(ValueError, match="PDF"):
        DrawingViewerModel(unsupported)


def test_window_zoom_rectangle_normalizes_drag_direction_and_rejects_tiny_selection():
    rect = ViewportRect.from_points(120, 90, 20, 10)
    assert (rect.left, rect.top, rect.right, rect.bottom) == (20, 10, 120, 90)
    assert rect.is_usable()
    assert not ViewportRect.from_points(1, 1, 2, 2).is_usable()


def test_region_geometry_requires_finite_nonzero_rectangle_and_explicit_scale():
    assert rectangle_to_points(10, 20, 0, 0) == ((0.0, 0.0), (10.0, 0.0), (10.0, 20.0), (0.0, 20.0))
    assert calibrated_rectangle_area(0, 0, 100, 50, 0.1) == 50.0
    for coords in [(0, 0, 0, 10), (0, 0, float("nan"), 10), (0, 0, 10, float("inf"))]:
        with pytest.raises(ValueError):
            rectangle_to_points(*coords)
    for scale in [0, -1, float("nan"), float("inf")]:
        with pytest.raises(ValueError):
            calibrated_rectangle_area(0, 0, 10, 10, scale)


def test_calibration_is_page_specific_and_missing_page_fails_closed():
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(page=1, reference_pixels=100, reference_meters=10)
    session.calibrate(page=2, reference_pixels=100, reference_meters=5)
    from core.drawings.graphical_takeoff import Point
    item1 = session.add_length([Point(0, 0), Point(100, 0)], page=1)
    item2 = session.add_length([Point(0, 0), Point(100, 0)], page=2)
    assert item1.quantity == 10
    assert item2.quantity == 5
    with pytest.raises(ValueError, match="کالیبره نشده"):
        session.add_length([Point(0, 0), Point(10, 0)], page=3)


def test_persian_cad_text_normalization_keeps_text_and_decodes_common_escapes():
    text = normalize_cad_text(r"\U+0645\U+0647\U+0646\U+062F\U+0633 %%d")
    assert text.startswith("مهندس")
    assert "°" in text
    assert is_rtl_cad_text(text)
    assert normalize_cad_text("  طبقه اول  ") == "طبقه اول"
