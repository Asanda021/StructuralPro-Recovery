import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession


def test_takeoff_session_rejects_zero_count_without_mutating_session():
    session = DrawingTakeoffSession("plan.pdf")
    with pytest.raises(ValueError, match="positive"):
        session.add_count(0, page=1)
    assert session.items == []
    assert session.can_undo is False


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
def test_takeoff_session_rejects_invalid_confidence_without_mutating_session(confidence):
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(page=1, reference_pixels=100, reference_meters=10)
    before = session.to_dict()
    with pytest.raises(ValueError, match="confidence"):
        session.add_length([Point(0, 0), Point(10, 0)], page=1, confidence=confidence)
    assert session.to_dict() == before


def test_takeoff_session_edit_validates_confidence_range():
    session = DrawingTakeoffSession("plan.pdf")
    session.calibrate(page=1, reference_pixels=100, reference_meters=10)
    item = session.add_count(1, page=1)
    with pytest.raises(ValueError, match="confidence"):
        session.edit(item.id, confidence=2)
    assert session.find(item.id).confidence == 1.0
