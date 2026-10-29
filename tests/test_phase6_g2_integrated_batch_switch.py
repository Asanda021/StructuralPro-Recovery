"""Phase 6 G2: the actual drawing->IFC worker->Qt 3D batch control chain.

Synthetic IFC4 fixtures only; independent published-reference acceptance runs
separately. All asserted views are read-only, from unmodified real IFC shapes.
"""
from __future__ import annotations

import hashlib
import time

import pytest
from PySide6.QtWidgets import QApplication

from test_phase6_p2_benchmark_ifc100 import make_ifc_floors


def _app():
    return QApplication.instance() or QApplication([])


def _await(app, condition, seconds=18):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return bool(condition())


def test_large_source_2d_preview_is_explicit_and_never_silent(tmp_path, monkeypatch):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.viewer_model import DrawingViewerModel
    path = tmp_path / "source.ifc"
    make_ifc_floors(path, 5)
    actual = DeepIFCAdapter.read_display_meshes

    def simulate_original_full_scene_capacity(self, source, **kw):
        if kw.get("selected_global_ids") is None:
            raise ValueError("مدل از ظرفیت نمایش مثلث‌ها بزرگ‌تر است.")
        return actual(self, source, **kw)

    monkeypatch.setattr(DeepIFCAdapter, "read_display_meshes",
                        simulate_original_full_scene_capacity)
    model = DrawingViewerModel()
    model.open(path)
    assert model.kind == "ifc"
    assert len(model.ifc_document.meshes) == 1
    assert len(model.ifc_document.source_roster) == 20
    assert len({r[0] for r in model.ifc_document.source_roster}) == 20
    assert model.ifc_document.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_dialog_filters_actual_source_roster_by_floor_type_and_pages(tmp_path):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    from app.ifc_3d_viewport import IFC3DDialog
    app = _app()
    path = tmp_path / "five-floors.ifc"
    make_ifc_floors(path, 5)
    import ifcopenshell
    model = ifcopenshell.open(str(path))
    first = next(x.GlobalId for x in model.by_type("IfcBeam"))
    contract = DeepIFCAdapter().read_display_contract(
        path, revision="R-1", selected_global_ids=[first], max_triangles=40000)
    dialog = IFC3DDialog(VerifiedScene3D(contract))
    try:
        assert dialog.batch_row.isVisible() is False or dialog.batch_row.isHidden() is False
        assert dialog.batch_type.count() == 5
        assert dialog.batch_storey.count() == 6
        dialog.batch_size.setValue(2)
        dialog.batch_type.setCurrentIndex(dialog.batch_type.findData("IfcDuctSegment"))
        assert len(dialog._filtered_batch_ids()) == 5
        assert dialog.batch_page.maximum() == 3
        dialog.batch_page.setValue(2)
        requested = []
        dialog.requestBatch.connect(lambda ids: requested.append(ids))
        assert dialog.request_selected_batch() is True
        assert len(requested) == 1 and len(requested[0]) == 2
        expected = {x.GlobalId for x in model.by_type("IfcDuctSegment")}
        assert set(requested[0]) <= expected
        floor = dialog.batch_storey.itemData(1)
        dialog.batch_storey.setCurrentIndex(1)
        assert len(dialog._filtered_batch_ids()) == 1
        assert dialog.batch_page.maximum() == 1
    finally:
        dialog.close()
        app.processEvents()


def test_atomic_scene_replace_keeps_valid_pick_and_revokes_stale_pick(tmp_path):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    from app.ifc_3d_viewport import IFC3DDialog
    app = _app()
    path = tmp_path / "swap.ifc"
    make_ifc_floors(path, 5)
    import ifcopenshell
    ids = sorted(m.GlobalId for m in ifcopenshell.open(str(path)).by_type("IfcElement"))
    source = DeepIFCAdapter()
    def scene(chosen):
        return VerifiedScene3D(source.read_display_contract(
            path, revision="R", selected_global_ids=chosen, max_triangles=40000))
    dialog = IFC3DDialog(scene(ids[:2]))
    observed = []
    dialog.memberSelected.connect(observed.append)
    try:
        dialog.canvas.choose_member(ids[0])
        assert dialog.replace_scene(scene(ids[:3])) is True
        assert dialog.canvas.selected_id == ids[0]
        assert not observed
        assert dialog.replace_scene(scene(ids[3:5])) is True
        assert dialog.canvas.selected_id is None
        assert observed == [""]
        assert {mesh.global_id for mesh in dialog.scene.meshes} == set(ids[3:5])
        assert dialog.scene.display_catalog["counts"] == {
            "displayed": 2, "not_loaded": 18, "without_geometry": 0,
        }
        prior = dialog.scene
        path.write_bytes(path.read_bytes() + b"\n/* altered source */")
        with pytest.raises(ValueError, match="تغییر"):
            dialog.replace_scene(prior)
        assert dialog.scene is prior
    finally:
        dialog.close()
        app.processEvents()


def test_main_ui_uses_worker_for_floor_and_type_batch_changes(tmp_path):
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app = _app()
    path = tmp_path / "main-ifc.ifc"
    make_ifc_floors(path, 5)
    main = GraphicalTakeoffDialog()
    try:
        main.ifc_revision.setText("R-MAIN")
        main.open_drawing(path)
        assert main.viewer.kind == "ifc"
        main.open_ifc_3d()
        assert _await(app, lambda: main._ifc_3d_loader is None, 18)
        window = main._ifc_3d_dialog
        assert window is not None and window.scene.display_catalog is not None
        assert window.scene.display_catalog["source_member_count"] == 20
        initial_scene = window.scene
        initial_hash = initial_scene.source_sha256
        window.batch_storey.setCurrentIndex(1)
        window.batch_type.setCurrentIndex(
            window.batch_type.findData("IfcDuctSegment"))
        assert len(window._filtered_batch_ids()) == 1
        target = window._filtered_batch_ids()[0]
        assert window.request_selected_batch() is True
        assert _await(app, lambda: main._ifc_3d_loader is None, 18)
        assert main._ifc_3d_dialog is window
        assert window.scene is not initial_scene
        assert window.scene.source_sha256 == initial_hash
        assert {m.global_id for m in window.scene.meshes} == {target}
        assert window.scene.display_catalog["counts"]["not_loaded"] == 19
        assert window.scene.quantity_authority is False
        assert not main.session.items
        # No BOQ, quantity or saved E2 mutation is performed by either batch.
    finally:
        main.cancel_ifc_3d_loading()
        view = getattr(main, "_ifc_3d_dialog", None)
        if view is not None:
            view.close()
        main.close()
        app.processEvents()


def test_normal_file_picker_subprocess_preserves_full_source_roster(tmp_path):
    """The user's ordinary IFC file-open path must use the same 3D catalog."""
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app = _app()
    source = tmp_path / "opened-through-worker.ifc"
    make_ifc_floors(source, 5)
    main = GraphicalTakeoffDialog()
    try:
        main.ifc_revision.setText("SUBPROCESS-R1")
        main.open_cad_async(source)
        assert _await(app, lambda: main._cad_job is None, 30)
        assert main.viewer.kind == "ifc", main.status.text()
        doc = main.viewer.ifc_document
        assert len(doc.source_roster) == 20
        assert len(doc.meshes) == 20
        assert doc.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
        main.open_ifc_3d()
        assert _await(app, lambda: main._ifc_3d_loader is None, 30)
        window = main._ifc_3d_dialog
        assert window is not None
        assert window.scene.display_catalog["source_member_count"] == 20
        assert window.batch_load.isEnabled()
    finally:
        main.cancel_ifc_3d_loading()
        main.cancel_cad_loading()
        window = getattr(main, "_ifc_3d_dialog", None)
        if window is not None:
            window.close()
        main.close()
        app.processEvents()
