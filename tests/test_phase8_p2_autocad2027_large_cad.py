"""P8P2: 2027 DWG-family signature, dense-scene memory and full CAD coverage.

Generated source fixtures are not the private user's drawing and do not
constitute final acceptance of proxy/AEC/MEP/3D engineering quantities.
"""
from itertools import repeat
from math import nan
from pathlib import Path

import pytest

from core.drawings.cad_large_scene import cad_coverage_report, cad_preview_index
from core.drawings.dwg_converter import OfflineDWGConverter
from core.drawings.dwg_takeoff import DWGDocument, DWGEntity, DWGTakeoffEngine


def test_autocad_2027_still_uses_ac1032_2018_dwg_signature(tmp_path: Path):
    # Autodesk 2027 format support contract: 2018-2027 save to AC1032.
    source = tmp_path / "autocad-2027-format.dwg"
    source.write_bytes(b"AC1032" + b"header-only-not-a-parseable-dwg")
    assert OfflineDWGConverter.inspect_header(source) == {
        "code": "AC1032", "version": "2018",
    }
    # Recognition != actual DWG parse/quantity acceptance.
    document = DWGDocument(dxf_version="AC1032")
    assert DWGTakeoffEngine().summarize(document)["autocad_format_through"] == 2027


def test_bounds_reduce_hundred_thousand_entities_without_vertex_buffer():
    obj = DWGEntity("LINE", "A-PLAN", "H1", {"start": (-12, 4), "end": (30, 17)})
    bounds, layers, types = cad_preview_index(repeat(obj, 125_000))
    assert bounds == (-12.0, 30.0, 4.0, 17.0)
    assert layers == {"A-PLAN": 125_000}
    assert types == {"LINE": 125_000}


def test_circle_extents_nonfinite_rejected_and_empty_drawing_bounded():
    circle = DWGEntity("CIRCLE", "A", "1", {"center": (30, -5), "radius": 7})
    bounds, _, _ = cad_preview_index([circle])
    assert bounds == (23.0, 37.0, -12.0, 2.0)
    assert cad_preview_index([])[0] == (0.0, 1.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="non-finite"):
        cad_preview_index([DWGEntity("LINE", "A", "X", {"start": (nan, 0)})])
    with pytest.raises(ValueError, match="circle radius"):
        cad_preview_index([DWGEntity("CIRCLE", "A", "2", {"center": (1, 1), "radius": -4})])


def test_all_source_types_accounted_even_when_not_drawn_or_payable():
    entities = [
        DWGEntity("LINE", "Visible", "1", {
            "start": (0, 0), "end": (2, 0), "length": 2, "layer_visible": True,
        }),
        DWGEntity("HATCH", "Visible", "2", {
            "pattern": "ANSI31", "unsupported_measurement": "boundaries missing",
        }),
        DWGEntity("ACAD_PROXY_ENTITY", "Visible", "3", {
            "unsupported_measurement": "requires object enabler",
        }),
        DWGEntity("INSERT", "Hidden", "4", {
            "insert": (0, 0), "layer_visible": False,
            "unsupported_measurement": "block must be expanded",
        }),
    ]
    document = DWGDocument(entities=entities, format="DWG_NATIVE_READONLY_PREVIEW",
                           dxf_version="AC1032")
    report = cad_coverage_report(document)
    assert report["source_entity_count"] == 4
    assert report["source_by_type"] == {
        "ACAD_PROXY_ENTITY": 1, "HATCH": 1, "INSERT": 1, "LINE": 1,
    }
    assert report["not_drawn_count"] == 3
    assert report["unmeasurable_count"] == 3
    assert report["hidden_layer_by_type"]["INSERT"] == 1
    assert report["all_entities_approved_for_takeoff"] is False
    summary = DWGTakeoffEngine().summarize(document)
    assert summary["coverage"] == report
    assert summary["autocad_format_through"] == 2027



def test_ellipses_and_splines_render_without_claiming_takeoff(tmp_path):
    import ezdxf
    drawing = ezdxf.new("R2018")
    drawing.header["$INSUNITS"] = 6
    model = drawing.modelspace()
    model.add_ellipse((0, 0), (4, 0), ratio=0.5)
    model.add_spline(fit_points=[(0, 0), (2, 4), (5, 0)])
    path = tmp_path / "2027-curves.dxf"
    drawing.saveas(path)
    document = DWGTakeoffEngine().import_file(path)
    by_type = {e.entity_type: e for e in document.entities}
    for typ in ("SPLINE", "ELLIPSE"):
        data = by_type[typ].data
        assert len(data["display_points"]) > 2
        assert data["unsupported_measurement"].startswith("نوع جزء")
        assert "length" not in data and "area" not in data
    coverage = cad_coverage_report(document)
    assert coverage["not_drawn_count"] == 0
    assert coverage["unmeasurable_count"] == 2
