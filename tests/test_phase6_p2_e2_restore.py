"""Real E2 persistence of 3D view state; no project/BOQ mutation."""
from copy import deepcopy
from pathlib import Path

import pytest

from test_phase6_p2_source_mesh3d import real_contract
from core.drawings.source_mesh3d import VerifiedScene3D
from core.drawings.ifc3d_session_state import capture_state, apply_state, save_to_e2, restore_from_e2
from core.platform.application import StructuralProApp


def setup(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.ifc_3d_viewport import IFC3DDialog
    app = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'app')
    service.create_project('مدل سه بعدی', 'P-3D')
    scene = VerifiedScene3D(real_contract(tmp_path))
    evidence = service.add_project_document('P-3D', scene.source_path)
    dialog = IFC3DDialog(scene, app_service=service, project_id='P-3D')
    return app, service, scene, dialog, evidence


def test_e2_real_project_snapshot_persists_after_closing_view_and_no_boq_changes(tmp_path):
    qt, service, scene, window, evidence = setup(tmp_path)
    try:
        window.show()
        scene.orbit(.25, -.1)
        scene.set_zoom(1.75)
        scene.pan(35, -20)
        window.canvas.choose_storey('Level-01')
        window.canvas.choose_member('IFC-WALL-01')
        window.isolate.setChecked(True)
        window.transparency.setChecked(True)
        window.section_height.setValue(1.25)
        window.section.setChecked(True)
        scene.hidden_storeys.add('Level-02')
        scene.hidden_types.add('IfcDuctSegment')
        expected = capture_state(scene, window.canvas)
        project_before = deepcopy(service.open_project('P-3D'))
        digest_before = service.store.current_digest('P-3D')
        assert window.save_e2_view(), window.session_status.text()
        snapshot_id = window.snapshot_id.text()
        assert len(snapshot_id) == 32
        assert service.open_project('P-3D') == project_before
        assert service.store.current_digest('P-3D') == digest_before
        window.close()
        scene2 = VerifiedScene3D(real_contract(tmp_path))
        from app.ifc_3d_viewport import IFC3DDialog
        new_window = IFC3DDialog(scene2, app_service=service, project_id='P-3D')
        try:
            new_window.snapshot_id.setText(snapshot_id)
            assert new_window.restore_e2_view(), new_window.session_status.text()
            assert capture_state(scene2, new_window.canvas) == expected
            assert new_window.section.isChecked() and new_window.isolate.isChecked()
            assert new_window.storey.currentData() == 'Level-01'
            assert service.store.current_digest('P-3D') == digest_before
            assert service.open_project('P-3D') == project_before
        finally:
            new_window.close()
    finally:
        window.close()
        service.store.close()


def test_e2_rejects_changed_ifc_bytes_or_wrong_revision_without_partial_state(tmp_path):
    qt, service, scene, view, evidence = setup(tmp_path)
    try:
        assert view.save_e2_view()
        sid = view.snapshot_id.text()
        alternate = VerifiedScene3D(real_contract(tmp_path))
        alternate.revision = 'R-OTHER'
        from app.ifc_3d_viewport import IFC3DDialog
        bad = IFC3DDialog(alternate, app_service=service, project_id='P-3D')
        try:
            initial = capture_state(alternate,bad.canvas)
            bad.snapshot_id.setText(sid)
            assert not bad.restore_e2_view()
            assert capture_state(alternate,bad.canvas) == initial
        finally: bad.close()
        Path(scene.source_path).write_bytes(b'changed bytes')
        assert not view.save_e2_view()
        assert not view.restore_e2_view()
    finally:
        view.close()
        service.store.close()


def test_e2_rejects_unregistered_source_and_unsupported_numeric_state(tmp_path):
    from core.platform.autosave import _checked_view
    from app.ifc_3d_viewport import IFC3DCanvas
    qt, service, scene, view, evidence = setup(tmp_path)
    try:
        state = capture_state(scene,view.canvas)
        malicious = {**state, 'yaw':float('nan')}
        with pytest.raises(ValueError):
            apply_state(scene,view.canvas,malicious)
        assert capture_state(scene,view.canvas)==state
        malicious = {**state, 'hidden_storeys':['UNREGISTERED']}
        with pytest.raises(ValueError):
            apply_state(scene,view.canvas,malicious)
        assert capture_state(scene,view.canvas)==state
        service.create_project('other', 'P-OTHER')
        with pytest.raises(ValueError):
            save_to_e2(service,'P-OTHER',scene,view.canvas)
    finally:
        view.close()
        service.store.close()
