import math
import pytest

from core.drawing.graphical_pdf_measurement_engine_v1 import (
    Calibration,
    MeasurementEvidence,
    Point,
    evidence_fingerprint,
    measure,
)


def _line():
    return MeasurementEvidence(
        project_id="P-01",
        revision="R1",
        source_id="PDF-01",
        page=2,
        element_id="E-01",
        geometry_type="line",
        points=(Point(0, 0), Point(3, 4)),
        calibration=Calibration(10.0, "PDF-01"),
    )


def test_line_measurement_uses_explicit_calibration():
    result = measure(_line())
    assert result.value == 50.0
    assert result.unit == "length"


def test_polygon_measurement_is_deterministic():
    evidence = MeasurementEvidence(
        project_id="P-01",
        revision="R1",
        source_id="PDF-01",
        page=1,
        element_id="E-02",
        geometry_type="polygon",
        points=(Point(0, 0), Point(2, 0), Point(2, 3), Point(0, 3)),
        calibration=Calibration(2.0, "PDF-01"),
    )
    assert measure(evidence).value == 24.0
    assert evidence_fingerprint(evidence) == evidence_fingerprint(evidence)


def test_missing_calibration_source_fails_closed():
    evidence = _line()
    bad = MeasurementEvidence(
        **{**evidence.__dict__, "calibration": Calibration(10.0, "OTHER")}
    )
    with pytest.raises(ValueError):
        measure(bad)


def test_invalid_scale_fails_closed():
    with pytest.raises(ValueError):
        Calibration(0, "PDF-01").validate()


def test_non_finite_geometry_fails_closed():
    evidence = MeasurementEvidence(
        **{**_line().__dict__, "points": (Point(0, 0), Point(math.nan, 4))}
    )
    with pytest.raises(ValueError):
        measure(evidence)


def test_polygon_requires_three_points():
    evidence = MeasurementEvidence(
        **{**_line().__dict__, "geometry_type": "polygon"}
    )
    with pytest.raises(ValueError):
        measure(evidence)
