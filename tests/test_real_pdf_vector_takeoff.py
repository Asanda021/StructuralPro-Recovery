import fitz
import pytest

from core.drawing.graphical_pdf_measurement_engine_v1 import (
    Calibration,
    MeasurementEvidence,
    Point,
    measure,
)


def make_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_line((10, 10), (20, 10))
    payload = doc.tobytes()
    doc.close()
    return payload


def test_real_pdf_can_supply_explicit_vector_evidence(tmp_path):
    path = tmp_path / "drawing.pdf"
    path.write_bytes(make_pdf())
    doc = fitz.open(path)
    page = doc[0]
    drawings = page.get_drawings()
    doc.close()

    assert drawings
    rect = drawings[0]["rect"]
    evidence = MeasurementEvidence(
        project_id="P1",
        revision="R1",
        source_id="drawing.pdf",
        page=1,
        element_id="vector-1",
        geometry_type="line",
        points=(Point(rect.x0, rect.y0), Point(rect.x1, rect.y1)),
        calibration=Calibration(units_per_page_unit=2.0, source_id="drawing.pdf"),
    )
    result = measure(evidence)
    assert result.unit == "length"
    assert result.value == pytest.approx(20.0)


def test_pdf_without_explicit_calibration_fails_closed():
    evidence = MeasurementEvidence(
        project_id="P1",
        revision="R1",
        source_id="drawing.pdf",
        page=1,
        element_id="vector-1",
        geometry_type="line",
        points=(Point(0, 0), Point(10, 0)),
        calibration=Calibration(units_per_page_unit=0.0, source_id="drawing.pdf"),
    )
    with pytest.raises(ValueError, match="positive"):
        measure(evidence)
