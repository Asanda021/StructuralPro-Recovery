import pytest

from core.drawing.adapters import AdapterResult, DrawingAdapterRegistry, DrawingSource
from core.drawing.models import DrawingPrimitive
from core.drawing.pipeline import DrawingIntelligencePipeline


class FakeScaledAdapter:
    extensions = (".p81",)

    def read(self, path):
        return AdapterResult(
            DrawingSource(path, "p81", {}),
            (
                DrawingPrimitive(
                    "line", x=0, y=0, x2=6000, y2=0,
                    layer="BEAM", source_id="p81:beam:1",
                ),
            ),
        )


def test_p81_measurement_gate_blocks_unscaled_boq(tmp_path):
    path = tmp_path / "plan.p81"
    path.write_text("placeholder", encoding="utf-8")
    result = DrawingIntelligencePipeline(
        adapters=DrawingAdapterRegistry(adapters=(FakeScaledAdapter(),))
    ).process(str(path))
    assert result.scale is None
    assert result.elements == ()
    assert result.quantity_candidates == ()
    assert result.boq == ()
    assert result.measurement_warnings


def test_p81_measurement_reaches_takeoff_and_boq_in_si_units(tmp_path):
    path = tmp_path / "plan.p81"
    path.write_text("placeholder", encoding="utf-8")
    result = DrawingIntelligencePipeline(
        adapters=DrawingAdapterRegistry(adapters=(FakeScaledAdapter(),))
    ).process(str(path), unit="mm")
    assert result.scale.coordinate_to_m == pytest.approx(0.001)
    assert result.elements[0].geometry["length"] == pytest.approx(6.0)
    assert result.elements[0].properties["measurement_formula"]
    assert result.quantity_candidates[0]["quantity"] == pytest.approx(6.0)
    assert result.boq[0]["quantity"] == pytest.approx(6.0)
    assert result.boq[0]["unit"] == "m"
