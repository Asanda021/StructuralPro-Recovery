"""E2 restored 3D selection feeds verified four-view signal, not a private UI state."""
from copy import deepcopy

import pytest

from test_phase6_p2_e2_restore import setup
from core.drawings.source_mesh3d import VerifiedScene3D
from test_phase6_p2_source_mesh3d import real_contract


@pytest.mark.parametrize("global_id", ["IFC-WALL-01", None])
def test_verified_e2_restored_member_or_cleared_selection_notifies_four_view(tmp_path,global_id):
    from app.ifc_3d_viewport import IFC3DDialog
    qt,service,scene,first,_document=setup(tmp_path)
    try:
        first.canvas.choose_member(global_id)
        first.canvas.choose_storey("Level-01")
        before=deepcopy(service.open_project("P-3D"))
        digest=service.store.current_digest("P-3D")
        assert first.save_e2_view(),first.session_status.text()
        sid=first.snapshot_id.text()
        after=IFC3DDialog(VerifiedScene3D(real_contract(tmp_path)),
                          app_service=service,project_id="P-3D")
        try:
            selected=[]
            after.memberSelected.connect(selected.append)
            after.snapshot_id.setText(sid)
            assert after.restore_e2_view(),after.session_status.text()
            assert selected==[global_id or ""]
            assert after.canvas.selected_id==global_id
            assert service.store.current_digest("P-3D")==digest
            assert service.open_project("P-3D")==before
        finally:
            after.close()
    finally:
        first.close()
        service.store.close()


def test_failed_e2_restore_never_notifies_stale_global_identity(tmp_path):
    from app.ifc_3d_viewport import IFC3DDialog
    qt,service,scene,first,_document=setup(tmp_path)
    try:
        first.canvas.choose_member("IFC-WALL-01")
        assert first.save_e2_view(),first.session_status.text()
        stale=IFC3DDialog(VerifiedScene3D(real_contract(tmp_path)),
                          app_service=service,project_id="P-3D")
        try:
            selected=[]
            stale.memberSelected.connect(selected.append)
            stale.scene.revision="STALE"
            stale.snapshot_id.setText(first.snapshot_id.text())
            assert not stale.restore_e2_view()
            assert selected==[]
        finally: stale.close()
    finally:
        first.close()
        service.store.close()
