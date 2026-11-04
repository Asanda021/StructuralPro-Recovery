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



def test_native_large_dwg_limits_are_explicit_and_sources_stay_immutable(tmp_path, monkeypatch):
    """Exercise exact source-entity cap without allocating a million objects."""
    from types import SimpleNamespace
    import sys
    from core.drawings import native_dwg_preview as preview
    assert preview._LIMIT_ENTITIES >= 1_000_000
    assert preview._LIMIT_BYTES >= 100 * 1024 * 1024
    path = tmp_path / "big-preview.dwg"
    path.write_bytes(b"AC1032" + b"synthetic-bounded-parser-evidence")
    before = path.read_bytes()

    class NativeLine:
        def __init__(self, index):
            self.dxftype = "LINE"
            self.handle = format(index+1, "X")
            self.dxf = {"layer_handle": 99, "start": (index, 0), "end": (index+1, 0)}

    class Model:
        def __init__(self, count):
            self.count = count

        def iter_entities(self):
            return (NativeLine(i) for i in range(self.count))

    class NativeDoc:
        version = "AC1032"
        units = "meters"
        layers = [SimpleNamespace(handle=99, name="A-STRUCT", on=True, frozen=False)]

        def __init__(self, count):
            self.count = count

        def modelspace(self):
            return Model(self.count)

    count = [3]
    monkeypatch.setattr(preview, "_LIMIT_ENTITIES", 3)
    monkeypatch.setattr(preview.util, "find_spec", lambda name: object())
    monkeypatch.setattr(preview.metadata, "version", lambda name: preview._EXPECTED_VERSION)
    monkeypatch.setitem(sys.modules, "ezdwg", SimpleNamespace(read=lambda name: NativeDoc(count[0])))
    doc = preview.native_readonly_dwg_preview(path)
    assert len(doc.entities) == 3
    assert doc.conversion["geometry_approved"] is False
    assert all("unsupported_measurement" in e.data for e in doc.entities)
    count[0] = 4
    with pytest.raises(ValueError, match="count exceeds"):
        preview.native_readonly_dwg_preview(path)
    assert path.read_bytes() == before


def test_viewer_uses_readonly_native_for_generic_strict_dwg_failure_only(tmp_path, monkeypatch):
    from core.drawings import native_dwg_preview as preview
    from core.drawings.viewer_model import DrawingViewerModel
    source = tmp_path / "proxy-rich.dwg"
    source.write_bytes(b"AC1032" + b"synthetic-proxy-fallback")
    expected = DWGDocument(
        source=str(source), format="DWG_NATIVE_READONLY_PREVIEW",
        source_sha256="synthetic-sha", dxf_version="AC1032",
        conversion={"preview_only": True, "geometry_approved": False},
        entities=[DWGEntity("ACAD_PROXY_ENTITY", "AEC", "A", {
            "unsupported_measurement": "requires object enabler",
        })],
    )

    def strict_fails(self, p):
        raise RuntimeError("proxy object strict decoder unsupported")

    monkeypatch.setattr(DWGTakeoffEngine, "import_file", strict_fails)
    monkeypatch.setattr(preview, "native_readonly_dwg_preview", lambda p: expected)
    viewer = DrawingViewerModel().open(source)
    assert viewer.cad_document is expected
    assert viewer.cad_document.conversion["geometry_approved"] is False
    assert any("Strict payable DWG import failed" in w for w in expected.warnings)

    def native_fails(p):
        raise ValueError("Native source invalid")

    monkeypatch.setattr(preview, "native_readonly_dwg_preview", native_fails)
    previous = viewer.path
    with pytest.raises(ValueError, match="Native source invalid"):
        viewer.open(source)
    assert viewer.path == previous
    assert viewer.cad_document is expected



def test_strict_cad_expansion_no_longer_rejects_more_than_250k_simple_entities():
    """No giant fixture: source identity is generated one item at a time."""
    from types import SimpleNamespace
    from core.drawings.dwg_takeoff import (
        _expanded_entities, _MAX_EXPANDED_CAD_ENTITIES,
    )
    assert _MAX_EXPANDED_CAD_ENTITIES >= 1_000_000

    class Dxf(dict):
        def __getattr__(self, key):
            return self[key]

    class Line:
        is_virtual = False

        def __init__(self, index):
            self.dxf = Dxf(handle=format(index+1, "X"), layer="A")

        def dxftype(self):
            return "LINE"

    doc = SimpleNamespace(layers={}, blocks={})
    extracted = _expanded_entities((Line(i) for i in range(250_001)), doc, [])
    assert sum(1 for _ in extracted) == 250_001


def test_strict_cad_expansion_hard_cap_is_fail_closed(monkeypatch):
    from types import SimpleNamespace
    from core.drawings import dwg_takeoff as mod

    class Dxf(dict):
        def __getattr__(self, key):
            return self[key]

    class Line:
        is_virtual = False

        def __init__(self, index):
            self.dxf = Dxf(handle=format(index+1, "X"), layer="A")

        def dxftype(self):
            return "LINE"

    monkeypatch.setattr(mod, "_MAX_EXPANDED_CAD_ENTITIES", 3)
    source = (Line(i) for i in range(4))
    with pytest.raises(ValueError, match="یک میلیون"):
        list(mod._expanded_entities(source, SimpleNamespace(layers={}, blocks={}), []))


def test_minsert_instances_reach_gui_parser_incrementally():
    """The second instance cannot be consumed before first child is emitted."""
    from types import SimpleNamespace
    from core.drawings.dwg_takeoff import _expanded_entities

    class Dxf(dict):
        def __getattr__(self, key):
            return self[key]

    class Line:
        is_virtual = False
        dxf = Dxf(handle="B1", layer="0")

        def dxftype(self):
            return "LINE"

    class Instance:
        def virtual_entities(self, skipped_entity_callback):
            yield Line()

    class Insert:
        is_virtual = False
        mcount = 2
        dxf = Dxf(handle="A1", layer="0", name="X", row_count=1, column_count=2,
                  column_spacing=4.0)

        def dxftype(self):
            return "INSERT"

        def multi_insert(self):
            yield Instance()
            raise AssertionError("Second MINSERT instance was materialized early")

    block = SimpleNamespace(block=SimpleNamespace(is_xref=False, is_xref_overlay=False))
    document = SimpleNamespace(layers={}, blocks={"X": block})
    output = _expanded_entities([Insert()], document, [], allow_arrays=True)
    first = next(output)
    assert first[1] == "A1"
    first_child = next(output)
    assert first_child[1] == "A1@0,0/B1"
