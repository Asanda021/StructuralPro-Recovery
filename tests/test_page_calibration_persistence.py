from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
import pytest


def test_page_specific_calibrations_survive_session_serialization():
    session = DrawingTakeoffSession("multi-page-plan.pdf")
    session.calibrate(page=1, reference_pixels=100, reference_meters=10)
    session.calibrate(page=2, reference_pixels=200, reference_meters=5)
    session.set_page(2)
    item = session.add_length([Point(0, 0), Point(200, 0)], page=2)
    assert item.quantity == 5

    restored = DrawingTakeoffSession.from_dict(session.to_dict())
    assert restored.current_page == 2
    assert restored.calibrations[1].meters_per_pixel == 0.1
    assert restored.calibrations[2].meters_per_pixel == 0.025
    assert restored.calibration.page == 2
    assert restored.validate()["valid"] is True
    restored.set_page(1)
    assert restored.calibration.page == 1


def test_from_dict_rejects_invalid_persisted_calibration():
    import pytest

    data = {
        "drawing_source": "plan.pdf",
        "current_page": 1,
        "calibrations": {
            "1": {
                "meters_per_pixel": 0,
                "page": 1,
                "reference_pixels": 100,
                "reference_meters": 10,
                "source": "manual-reference",
            }
        },
        "items": [],
        "markups": [],
    }
    with pytest.raises(ValueError, match="کالیبراسیون نامعتبر"):
        DrawingTakeoffSession.from_dict(data)


def test_recalibration_never_leaves_existing_measurements_on_stale_scale():
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(1, 100, 10)
    item = session.add_length([Point(0, 0), Point(100, 0)])
    before = session.to_dict()
    with pytest.raises(ValueError, match="متره ثبت‌شده"):
        session.calibrate(1, 100, 20)
    assert session.to_dict() == before
    session.remove(item.id)
    session.calibrate(1, 100, 20)
    assert session.add_length([Point(0, 0), Point(100, 0)]).quantity == 20


def test_bridge_rejects_reference_and_factor_disagreement():
    from core.drawings.takeoff_bridge import validate_session_payload
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(1, 100, 10)
    session.add_length([Point(0, 0), Point(100, 0)])
    data = session.to_dict()
    data["calibrations"]["1"]["meters_per_pixel"] = .2
    assert not validate_session_payload(data)["valid"]


@pytest.mark.parametrize("page", [True, 1.5, float("inf"), 0])
def test_page_identity_is_never_truncated_or_coerced_from_boolean(page):
    session = DrawingTakeoffSession("plan.pdf")
    with pytest.raises(ValueError):
        session.set_page(page)
    with pytest.raises(ValueError):
        session.calibrate(page, 100, 10)
    with pytest.raises(ValueError):
        session.add_count(1, page=page)


def test_invalid_confidence_does_not_consume_identity_or_change_history():
    session = DrawingTakeoffSession("plan.pdf")
    before = session.to_dict()
    with pytest.raises(ValueError):
        session.add_count(1, confidence=float("nan"))
    assert session.to_dict() == before
    assert not session.can_undo
    assert session.add_count(1).id == "TO-00001"
