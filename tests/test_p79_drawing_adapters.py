from pathlib import Path

import pytest

from core.drawing.adapters import (
    AdapterResult,
    DrawingAdapterRegistry,
    DrawingSource,
    PDFAdapter,
)
from core.drawing.models import DrawingPrimitive
from core.drawing.pipeline import DrawingIntelligencePipeline


class FakeAdapter:
    extensions = (".fake",)

    def read(self, path):
        return AdapterResult(
            DrawingSource(Path(path), "fake", {}),
            (
                DrawingPrimitive(
                    "line", x=0, y=0, x2=6, y2=0,
                    layer="BEAM", source_id="fake:beam:1",
                ),
                DrawingPrimitive(
                    "text", text="COL-2", source_id="fake:column:2",
                ),
            ),
        )


def test_registry_routes_by_real_source_extension():
    registry = DrawingAdapterRegistry(adapters=(FakeAdapter(),))
    assert isinstance(registry.for_path("plan.fake"), FakeAdapter)


def test_registry_rejects_unsupported_source():
    with pytest.raises(ValueError, match="unsupported drawing source"):
        DrawingAdapterRegistry(adapters=(FakeAdapter(),)).for_path("plan.xyz")


def test_pipeline_connects_adapter_intelligence_standards_takeoff_and_boq(tmp_path):
    source = tmp_path / "plan.fake"
    source.write_text("placeholder", encoding="utf-8")

    result = DrawingIntelligencePipeline(
        adapters=DrawingAdapterRegistry(adapters=(FakeAdapter(),))
    ).process(str(source), unit="m")

    assert [e.kind for e in result.elements] == ["beam", "column"]
    assert result.boq[0]["source"] == "fake:beam:1"
    assert result.boq[0]["quantity"] == 6
    assert result.boq[0]["unit"] == "m"
    assert result.standards["fake:beam:1"]
    assert result.adapter_warnings == ()
    assert result.measurement_warnings == ()
    assert result.scale.unit == "m"


def test_pdf_adapter_keeps_page_and_source_traceability(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    path = tmp_path / "drawing.pdf"
    with path.open("wb") as handle:
        writer.write(handle)

    result = PDFAdapter().read(path)
    assert result.source.kind == "pdf"
    assert result.source.metadata["page_count"] == 1
    assert result.primitives == ()
    assert result.warnings


def test_operational_pipeline_fails_closed_without_drawing_unit(tmp_path):
    source = tmp_path / "plan.fake"
    source.write_text("placeholder", encoding="utf-8")
    result = DrawingIntelligencePipeline(
        adapters=DrawingAdapterRegistry(adapters=(FakeAdapter(),))
    ).process(str(source))
    assert result.scale is None
    assert result.quantity_candidates == ()
    assert result.boq == ()
    assert result.measurement_warnings

def test_operational_pipeline_converts_explicit_drawing_unit_to_si(tmp_path):
    source = tmp_path / "plan.fake"
    source.write_text("placeholder", encoding="utf-8")
    result = DrawingIntelligencePipeline(
        adapters=DrawingAdapterRegistry(adapters=(FakeAdapter(),))
    ).process(str(source), unit="cm")
    assert result.scale.coordinate_to_m == pytest.approx(0.01)
    assert result.boq[0]["quantity"] == pytest.approx(0.06)
    assert result.elements[0].properties["measurement_formula"]
