import pytest
from core.drawing.models import DrawingPrimitive
from core.drawing.measurement import primitive_measurements, scale_from_metadata, scale_from_unit

def test_measurement_metadata_and_units_remain_auditable():
    m = primitive_measurements(
        (DrawingPrimitive("line", x=0, y=0, x2=6000, y2=0, source_id="L1"),),
        scale_from_unit("mm"),
    )[0]
    assert m.value == pytest.approx(6.0)
    assert m.unit == "m"
    assert m.source_ids == ("L1",)
    assert "coordinate_to_m" in m.formula

def test_metadata_scale_is_explicit():
    scale = scale_from_metadata({"unit": "m", "scale_denominator": 100})
    assert scale.coordinate_to_m == pytest.approx(100.0)
    assert scale.source == "source-metadata"

def test_unknown_unit_is_not_assumed():
    assert scale_from_metadata({"layer": "BEAM"}) is None

def test_invalid_unit_fails_closed():
    with pytest.raises(ValueError):
        scale_from_unit("banana")
