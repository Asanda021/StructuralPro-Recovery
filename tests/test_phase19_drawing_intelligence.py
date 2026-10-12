"""Phase 19 acceptance tests."""
from pathlib import Path

from core.drawing.models import DrawingPrimitive
from core.drawing.adapters import AdapterResult, DrawingAdapterRegistry, DrawingSource
from core.drawing.phase19 import DrawingIntelligenceWorkflow


class FakeAdapter:
    extensions = (".draw",)

    def read(self, path):
        p = Path(path)
        primitives = (
            DrawingPrimitive("text", text="A101", source_id="sheet", properties={"page": 1}),
            DrawingPrimitive("text", text="ZONE Z1", source_id="zone", properties={"page": 1}),
            DrawingPrimitive("text", text="DIM: 6000 mm", source_id="dim", properties={"page": 1}),
            DrawingPrimitive("line", x=0, y=0, x2=10, y2=0, layer="beam",
                             source_id="beam-1", properties={"page": 1}),
            DrawingPrimitive("line", x=0, y=0, x2=10, y2=0, layer="beam",
                             source_id="beam-1", properties={"page": 1}),
        )
        return AdapterResult(
            DrawingSource(p, "draw", {"page_count": 1, "unit": "m", "scale_denominator": 1}),
            primitives,
        )


def workflow():
    return DrawingIntelligenceWorkflow(
        DrawingAdapterRegistry((FakeAdapter(),))
    )


def test_p19_detects_sheets_zones_dimensions_and_links_measurement_to_boq():
    result = workflow().analyze("sample.draw")
    assert len(result.sheets) == 1
    assert result.sheets[0].sheet_id == "A101"
    assert result.zones[0].key == "Z1"
    assert result.dimensions[0].value == 6000
    assert result.scale is not None
    assert len(result.elements) == 1
    assert len(result.measurements) == 1
    link = result.measurement_links[0]
    assert link.element_id == result.elements[0].element_id
    assert link.boq_key.startswith("drawing:") or link.boq_key.startswith("structural:")


def test_p19_duplicate_geometry_is_suppressed_before_intelligence():
    result = workflow().analyze("sample.draw")
    assert len(result.elements) == 1
    assert len(result.measurements) == 1


def test_p19_missing_scale_fails_closed():
    class NoScaleAdapter(FakeAdapter):
        def read(self, path):
            result = super().read(path)
            return AdapterResult(
                result.source.__class__(result.source.path, "draw", {"page_count": 1, "unit": "m"}),
                result.primitives,
                result.warnings,
            )

    wf = DrawingIntelligenceWorkflow(DrawingAdapterRegistry((NoScaleAdapter(),)))
    result = wf.analyze("sample.draw")
    assert result.scale is None
    assert not result.measurements
    assert not result.measurement_links
    assert any("scale" in warning.lower() for warning in result.warnings)


def test_p19_scale_without_unit_fails_closed():
    class NoUnitAdapter(FakeAdapter):
        def read(self, path):
            result = super().read(path)
            return AdapterResult(
                result.source.__class__(result.source.path, "draw", {"page_count": 1, "scale_denominator": 100}),
                result.primitives,
                result.warnings,
            )

    wf = DrawingIntelligenceWorkflow(DrawingAdapterRegistry((NoUnitAdapter(),)))
    result = wf.analyze("sample.draw")
    assert result.scale is None
    assert not result.measurements
    assert not result.measurement_links
    assert any("unit" in warning.lower() for warning in result.warnings)
