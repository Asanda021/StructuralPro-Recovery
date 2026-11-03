"""SYNTHETIC decoder-boundary regressions; private CAD is never uploaded."""
from math import hypot
from types import SimpleNamespace
import os

import pytest

from core.drawings.native_dwg_preview import native_readonly_dwg_preview
from core.drawings.cad_large_scene import cad_coverage_report
from core.drawings.dwg_takeoff import cad_entity_geometry


def preview(tmp_path, monkeypatch, objects, on_read=None):
    import ezdwg
    source = tmp_path / "decoder-boundary.dwg"
    source.write_bytes(b"AC1018_SYNTHETIC_DECODER_BOUNDARY_NOT_A_REAL_DWG")
    layer = SimpleNamespace(handle=1, name="source", on=True, frozen=False)
    raw = SimpleNamespace(version="AC1018", units="unitless", layers=[layer],
                          modelspace=lambda: SimpleNamespace(iter_entities=lambda: iter(objects)))
    def read(path):
        if on_read:
            on_read(source)
        return raw
    monkeypatch.setattr(ezdwg, "read", read)
    return native_readonly_dwg_preview(source)


def obj(typ, handle="1", **data):
    return SimpleNamespace(dxftype=typ, handle=handle, dxf={"layer_handle": 1, **data})


def test_native_arc_reaches_display_with_correct_sweep(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("ARC", center=(10, 20, 0), radius=2,
                                           start_angle=350, end_angle=10)])
    points = doc.entities[0].data["display_points"]
    assert points[0][1] < 20 < points[-1][1]
    assert all(x > 11.9 for x, y in points)  # 20-degree arc, not a 340-degree arc
    assert all(hypot(x-10, y-20) == pytest.approx(2, rel=0.001) for x, y in points)
    assert cad_coverage_report(doc)["not_drawn_count"] == 0
    with pytest.raises(ValueError, match="فقط"):
        cad_entity_geometry(doc, "1", "length")


def test_native_bulge_polyline_is_curved_instead_of_chord(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("LWPOLYLINE", points=[(0,0,0),(2,0,0)],
                                           bulges=[1,0], closed=False)])
    points = doc.entities[0].data["display_points"]
    assert len(points) > 4
    assert min(y for x,y in points) < -0.99
    assert points[0] == pytest.approx((0,0))
    assert points[-1] == pytest.approx((2,0))


def test_dimension_uses_source_text_midpoint_and_keeps_raw_text(tmp_path, monkeypatch):
    raw = "كیفیت \\P آزمايش"
    doc = preview(tmp_path, monkeypatch, [obj("DIMENSION", text=raw,
                insert=(0,0,0), text_midpoint=(12,34,0), text_rotation=30)])
    d = doc.entities[0].data
    assert d["source_text"] == raw
    assert d["insert"] == (12,34)
    assert d["rotation"] == 30
    assert doc.conversion["text_fidelity"] != "VERIFIED"




def test_native_shx_text_handles_are_preserved_without_guessing_glyph_mapping(tmp_path, monkeypatch):
    # Synthetic samples model three rejected-style identities. They are NOT
    # evidence that the private 38 TEXT records were accepted or decoded.
    entries = [
        obj("TEXT", "F110", text="\\x7f" + "\u00D8\u00AA", style_handle="A1",
            text_generation_flag=2, insert=(1, 2, 0)),
        obj("TEXT", "F111", text="a\\U+0628", style_handle="B2",
            text_generation_flag=0, insert=(3, 4, 0)),
        obj("TEXT", "F112", text="%%c", style_handle="C3",
            text_generation_flag=0, insert=(5, 6, 0)),
    ]
    doc = preview(tmp_path, monkeypatch, entries)
    assert [entity.handle for entity in doc.entities] == ["F110", "F111", "F112"]
    assert [entity.data["source_text"] for entity in doc.entities] == [
        entry.dxf["text"] for entry in entries
    ]
    assert [entity.data["style_handle"] for entity in doc.entities] == [
        "A1", "B2", "C3"
    ]
    assert doc.conversion["native_text_entity_count"] == 3
    assert doc.conversion["native_text_decoded_preserved_count"] == 3
    assert doc.conversion["native_text_style_handles"] == {
        "B2": 1, "C3": 1, "A1": 1
    }
    assert doc.conversion["native_text_mapping_approved"] is False
    assert doc.conversion["native_text_financial_approval"] is False
    assert all(not entity.data["source_text_mapping_approved"] for entity in doc.entities)
    assert all(entity.data["preview_only"] for entity in doc.entities)
    assert doc.units == "unitless"
    with pytest.raises(ValueError, match="فقط"):
        cad_entity_geometry(doc, "F110", "count")

def test_native_invisible_entity_does_not_become_visible(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("LINE", start=(0,0,0), end=(1,1,0), invisible=True)])
    assert doc.entities[0].data["layer_visible"] is False
    assert cad_coverage_report(doc)["hidden_layer_by_type"] == {"LINE":1}


def test_native_spline_uses_control_points_and_knots(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("SPLINE", degree=2,
                control_points=[(0,0,0),(1,2,0),(2,0,0)], knots=[0,0,0,1,1,1],
                weights=[], closed=False)])
    points = doc.entities[0].data["display_points"]
    assert max(y for x,y in points) == pytest.approx(1, abs=.01)
    assert cad_coverage_report(doc)["not_drawn_count"] == 0


def test_native_hatch_loops_stay_separate_and_nonpayable(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("HATCH", paths=[
        {"closed":True,"points":[(0,0),(5,0),(5,5),(0,5)]},
        {"closed":True,"points":[(1,1),(2,1),(2,2),(1,2)]}])])
    paths = doc.entities[0].data["display_paths"]
    assert len(paths) == 2
    assert all(p[0] == p[-1] for p in paths)
    assert doc.entities[0].data["unsupported_measurement"]
    assert cad_coverage_report(doc)["not_drawn_count"] == 0


def test_native_bad_geometry_is_accounted_and_not_drawn(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("ARC", center=(0,0,0), radius=-1,
                                           start_angle=0, end_angle=90)])
    assert doc.entities[0].data["preview_decode_error"]
    assert cad_coverage_report(doc)["failed_geometry_count"] == 1
    assert cad_coverage_report(doc)["not_drawn_count"] == 1


def test_native_same_bytes_replacement_is_not_the_original_identity(tmp_path, monkeypatch):
    def replace(source):
        replacement=source.with_suffix(".replacement")
        replacement.write_bytes(source.read_bytes())
        os.replace(replacement, source)
    with pytest.raises(ValueError, match="changed|تغییر"):
        preview(tmp_path, monkeypatch, [obj("LINE", start=(0,0), end=(1,1))], replace)


def test_native_accounting_is_disjoint_without_claiming_decoder_completeness(tmp_path, monkeypatch):
    doc = preview(tmp_path, monkeypatch, [obj("LINE", "1", start=(0,0), end=(1,1)),
        obj("INSERT", "2", name="unresolved", insert=(2,2)),
        obj("TEXT", "3", text="كي", insert=(1,1))])
    report=cad_coverage_report(doc)
    assert report["decoded_entity_count"] == 3
    assert sum(report["display_partition"].values()) == 3
    assert report["original_source_count_verified"] is False
    assert report["complete_visual_fidelity"] is False  # unresolved block/font


def test_qt_canvas_receives_native_arc_and_separate_hatch_rings(tmp_path,monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app=QApplication.instance() or QApplication([])
    doc=preview(tmp_path,monkeypatch,[obj("ARC","1",center=(0,0,0),radius=2,
                  start_angle=0,end_angle=90),obj("HATCH","2",paths=[
                 {"closed":True,"points":[(0,0),(5,0),(5,5),(0,5)]},
                 {"closed":True,"points":[(1,1),(2,1),(2,2),(1,2)]}])])
    dialog=GraphicalTakeoffDialog()
    try:
        dialog.cad_document=doc
        dialog._render_cad()
        assert set(dialog._cad_handle_items)=={"1","2"}
        assert dialog._cad_handle_items["1"].path().elementCount()>4
        hatch=dialog._cad_handle_items["2"].path()
        assert sum(hatch.elementAt(i).isMoveTo() for i in range(hatch.elementCount()))==2
    finally:
        dialog.close();dialog.deleteLater();app.processEvents()


def test_boundary_only_solid_does_not_claim_complete_filled_fidelity(tmp_path,monkeypatch):
    doc=preview(tmp_path,monkeypatch,[obj("SOLID",points=[(0,0),(1,0),(0,1),(1,1)])])
    assert cad_coverage_report(doc)["not_drawn_count"]==0
    assert cad_coverage_report(doc)["complete_visual_fidelity"] is False


@pytest.mark.parametrize("reopen_payable", [False, True])
def test_async_busy_restore_respects_actual_new_source_capability(tmp_path,monkeypatch,reopen_payable):
    os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from core.drawings.dwg_takeoff import DWGDocument
    from core.platform.application import StructuralProApp
    app=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'projects')
    dialog=GraphicalTakeoffDialog(app_service=service)
    try:
        # Reproduce completion/cancel control restoration, using a synthetic
        # decoded source boundary. Real DWG/strict import is covered separately.
        dialog._cad_busy(True)
        dialog.viewer.kind='cad';dialog.viewer.path=tmp_path/'source.dwg'
        dialog.cad_document=DWGDocument(format='DWG_NATIVE_READONLY_PREVIEW')
        dialog.canvas.read_only_model=True
        for button in (dialog.cad_measure,dialog.cad_review,dialog.commit_boq_button):button.setEnabled(False)
        dialog._cad_busy(False)
        dialog.refresh()
        assert not dialog.cad_measure.isEnabled()
        assert not dialog.cad_review.isEnabled()
        assert not dialog.commit_boq_button.isEnabled()
        assert not dialog.mode.isEnabled()
        if reopen_payable:
            dialog._cad_busy(True)
            dialog.cad_document=DWGDocument(format='DXF',units='m')
            dialog.canvas.read_only_model=False
            dialog._cad_busy(False)
            assert dialog.cad_measure.isEnabled()
            assert dialog.cad_review.isEnabled()
            assert dialog.commit_boq_button.isEnabled()
    finally:
        dialog.close();dialog.deleteLater();app.processEvents()
