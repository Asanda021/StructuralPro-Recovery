import math
import pytest


def test_cad_layer_length_fails_closed_when_dxf_units_are_unknown(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from core.drawings.dwg_takeoff import DWGTakeoffEngine

    path = tmp_path / "unitless.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 0
    doc.modelspace().add_line((0, 0), (1000, 0), dxfattribs={"layer": "WALL"})
    doc.saveas(path)
    engine = DWGTakeoffEngine()
    parsed = engine.import_file(path)
    with pytest.raises(ValueError, match="واحد نقشه"):
        engine.layer_takeoff(parsed, {"WALL": {"metric": "length"}})


def test_cad_layer_takeoff_normalizes_known_units_and_requires_review(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from core.drawings.dwg_takeoff import DWGTakeoffEngine

    path = tmp_path / "millimeters.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    doc.modelspace().add_line((0, 0), (1000, 0), dxfattribs={"layer": "WALL"})
    doc.saveas(path)
    engine = DWGTakeoffEngine()
    parsed = engine.import_file(path)
    rows = engine.layer_takeoff(parsed, {"WALL": {"metric": "length"}})
    assert rows[0]["quantity"] == pytest.approx(1.0)
    assert rows[0]["unit"] == "m"
    assert rows[0]["needs_confirmation"] is True
    assert rows[0]["unit_basis"] == "mm"


def test_cad_layer_takeoff_rejects_unsupported_metric(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from core.drawings.dwg_takeoff import DWGTakeoffEngine

    path = tmp_path / "drawing.dxf"
    doc = ezdxf.new("R2018")
    doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "WALL"})
    doc.saveas(path)
    parsed = DWGTakeoffEngine().import_file(path)
    with pytest.raises(ValueError, match="متریک"):
        DWGTakeoffEngine().layer_takeoff(parsed, {"WALL": {"metric": "volume"}})


def test_pdf_engine_rejects_bad_page_and_snap_non_finite_inputs(tmp_path):
    fitz = pytest.importorskip("fitz")
    from core.drawings.pdf_engine import PDFDrawingEngine

    path = tmp_path / "one-page.pdf"
    doc = fitz.open()
    doc.new_page(width=300, height=200)
    doc.save(path)
    doc.close()
    with PDFDrawingEngine(path) as engine:
        assert engine.page_count == 1
        with pytest.raises(IndexError):
            engine.text(0)
        with pytest.raises(IndexError):
            engine.render(2)
        with pytest.raises(ValueError):
            engine.render(1, dpi=0)
        assert engine.snap((1, 1), []) == (1.0, 1.0)
        with pytest.raises(ValueError):
            engine.snap((math.nan, 1), [])


def test_viewer_failed_pdf_open_does_not_replace_existing_cad(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from core.drawings.viewer_model import DrawingViewerModel

    cad_path = tmp_path / "valid.dxf"
    dxf = ezdxf.new("R2018")
    dxf.modelspace().add_line((0, 0), (10, 0))
    dxf.saveas(cad_path)
    viewer = DrawingViewerModel(cad_path)
    corrupt_pdf = tmp_path / "broken.pdf"
    corrupt_pdf.write_bytes(b"not a pdf")
    with pytest.raises(Exception):
        viewer.open(corrupt_pdf)
    assert viewer.path == cad_path
    assert viewer.kind == "cad"
    assert viewer.page_count == 1
