import pytest


def test_viewer_rejects_missing_file(tmp_path):
    from core.drawings.viewer_model import DrawingViewerModel

    with pytest.raises(FileNotFoundError):
        DrawingViewerModel(tmp_path / "missing.pdf")


def test_viewer_rejects_unsupported_extension(tmp_path):
    from core.drawings.viewer_model import DrawingViewerModel

    path = tmp_path / "drawing.txt"
    path.write_text("not a drawing", encoding="utf-8")
    with pytest.raises(ValueError):
        DrawingViewerModel(path)


def test_viewer_opens_real_dxf_and_exposes_summary(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    from core.drawings.viewer_model import DrawingViewerModel

    path = tmp_path / "plan.dxf"
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "STRUCT"})
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 5), (0, 5)], close=True,
                       dxfattribs={"layer": "WALL"})
    doc.saveas(path)

    viewer = DrawingViewerModel(path)
    assert viewer.kind == "cad"
    assert viewer.page_count == 1
    assert viewer.summary["entities"] >= 2
    assert "STRUCT" in viewer.summary["layers"]
    assert viewer.clamp_page(99) == 1
