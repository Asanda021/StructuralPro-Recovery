"""Deterministic regression evidence, not independent real-project acceptance."""
import math

import pytest

from core.drawings.dwg_takeoff import DWGTakeoffEngine, _poly_metrics
from core.drawings.viewer_model import DrawingViewport


@pytest.mark.parametrize("bulge", [1, -1])
def test_cad_semicircle_uses_arc_length_and_segment_area(bulge):
    length, area = _poly_metrics([(0, 0), (10, 0), (0, 0)], True, [bulge, 0, 0])
    assert length == pytest.approx(5 * math.pi + 10)
    assert area == pytest.approx(25 * math.pi / 2)


def test_real_dxf_file_preserves_curved_geometry_and_explicit_units(tmp_path):
    import ezdxf
    path = tmp_path / "curved.dxf"
    doc = ezdxf.new("R2018")
    doc.units = 6
    doc.modelspace().add_lwpolyline([(0, 0, 1), (10, 0, 0), (0, 0, 0)], format="xyb", close=True)
    doc.modelspace().add_text("دیوار منحنی")
    doc.saveas(path)
    loaded = DWGTakeoffEngine().import_file(path)
    curve = next(item for item in loaded.entities if item.entity_type == "LWPOLYLINE")
    assert loaded.units == "m"
    assert "دیوار منحنی" in loaded.text_labels
    assert curve.data["length"] == pytest.approx(5 * math.pi + 10)
    assert curve.data["area"] == pytest.approx(25 * math.pi / 2)
    assert len(curve.data["display_points"]) > 3
    assert curve.data["closed"]


def test_dxf_display_keeps_open_polyline_arc_circle_and_text_position(tmp_path):
    import ezdxf
    path = tmp_path / "display.dxf"
    doc = ezdxf.new("R2018")
    doc.units = 4
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (1000, 0), (1000, 1000)])
    msp.add_arc((2000, 2000), 1000, 0, 180)
    msp.add_circle((4000, 4000), 500)
    msp.add_text("ستون", dxfattribs={"insert": (1000, 2000), "height": 200})
    doc.saveas(path)
    entities = {item.entity_type: item.data for item in DWGTakeoffEngine().import_file(path).entities}
    assert not entities["LWPOLYLINE"]["closed"]
    assert len(entities["ARC"]["display_points"]) > 2
    assert entities["CIRCLE"]["center"] == (4, 4)
    assert entities["CIRCLE"]["radius"] == .5
    assert entities["TEXT"]["insert"] == (1, 2)
    assert entities["TEXT"]["height"] == .2


@pytest.mark.parametrize("viewport", [DrawingViewport(0, 0, 0, 10), DrawingViewport(float("nan"), 0, 10, 10)])
def test_zoom_window_rejects_degenerate_and_nonfinite_geometry(viewport):
    with pytest.raises(ValueError):
        viewport.normalized()


def test_large_pdf_stops_before_allocating_unsafe_render(tmp_path):
    import fitz
    from core.drawings.pdf_engine import PDFDrawingEngine
    path = tmp_path / "large.pdf"
    doc = fitz.open()
    doc.new_page(width=5000, height=5000)
    doc.save(path)
    doc.close()
    with PDFDrawingEngine(path) as reader:
        with pytest.raises(ValueError, match="وضوح پایین‌تر"):
            reader.render(1, dpi=600)
        assert reader.render(1, dpi=36).startswith(b"\x89PNG")


def test_actual_qt_viewer_does_not_close_open_cad_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import ezdxf
    from PySide6.QtWidgets import QApplication, QGraphicsPathItem
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "open-path.dxf"
    doc = ezdxf.new("R2018")
    doc.units = 6
    doc.modelspace().add_lwpolyline([(0, 0), (10, 0), (10, 10)])
    doc.saveas(path)
    dialog = GraphicalTakeoffDialog()
    try:
        dialog.cad_document = DWGTakeoffEngine().import_file(path)
        dialog._render_cad()
        paths = [item.path() for item in dialog.canvas.scene.items() if isinstance(item, QGraphicsPathItem)]
        assert len(paths) == 1
        assert paths[0].elementCount() == 3
        assert paths[0].elementAt(0).x != paths[0].elementAt(2).x
    finally:
        dialog.close()
        app.processEvents()


def test_polyface_mesh_is_preserved_without_inventing_planar_measurement(tmp_path):
    import ezdxf
    path = tmp_path / "mesh.dxf"
    doc = ezdxf.new("R2018")
    doc.units = 6
    mesh = doc.modelspace().add_polyface(dxfattribs={"layer": "MESH"})
    mesh.append_faces([[(0, 0, 0), (1, 0, 1), (1, 1, 2), (0, 1, 1)]])
    doc.modelspace().add_line((0, 0), (2, 0))
    doc.saveas(path)
    engine = DWGTakeoffEngine()
    parsed = engine.import_file(path)
    item = next(e for e in parsed.entities if e.entity_type == "POLYLINE")
    assert item.data["mesh_vertices"]
    assert item.data["unsupported_measurement"]
    assert "length" not in item.data and "area" not in item.data
    assert engine.summarize(parsed)["unsupported_geometry_count"] == 1
    with pytest.raises(ValueError, match="شبکه سه‌بعدی"):
        engine.layer_takeoff(parsed, {"MESH": {"metric": "area"}})
