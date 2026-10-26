"""End-to-end E2 application boundary: real SQLite, ACL, documents and revision."""
import pytest
from core.platform.application import StructuralProApp
from test_phase5_p3_trusted_identity_store import SwitchingIdentityProvider, identity


def test_e2_real_app_reopen_restores_view_only_with_same_revision(tmp_path):
    ids=SwitchingIdentityProvider(identity("user:A","Alice"))
    directory=tmp_path/"app"
    service=StructuralProApp(directory,identity_provider=ids)
    service.create_project("پنج طبقه","P")
    source=tmp_path/"plan.pdf"
    source.write_bytes(b"trusted plan")
    document=service.add_project_document("P",source)
    project=service.open_project("P")
    original_revision=project["_meta"]["version"]
    original_boq=project["boq"]
    receipt=service.save_view_session("P",{
        "document_id":document["id"],"current_tab":"takeoff","zoom_2d":1.25,
    })
    assert receipt["revision"]==original_revision
    assert service.open_project("P")["_meta"]["version"]==original_revision
    assert service.open_project("P")["boq"]==original_boq
    service.store.close()
    reopened=StructuralProApp(directory,identity_provider=ids)
    try:
        view=reopened.restore_view_session("P",receipt["snapshot_id"])
        assert view["document_id"]==document["id"] and view["zoom_2d"]==1.25
        assert reopened.open_project("P")["_meta"]["version"]==original_revision
    finally:
        reopened.store.close()


def test_e2_real_app_does_not_restore_when_source_or_revision_changes(tmp_path):
    ids=SwitchingIdentityProvider(identity("user:A","Alice"))
    service=StructuralProApp(tmp_path/"app",identity_provider=ids)
    service.create_project("project","P")
    file=tmp_path/"source.pdf"
    file.write_bytes(b"original")
    d=service.add_project_document("P",file)
    receipt=service.save_view_session("P",{"document_id":d["id"]})
    file.write_bytes(b"tampered")
    with pytest.raises(ValueError,match="source evidence"):
        service.restore_view_session("P",receipt["snapshot_id"])
    file.write_bytes(b"original")
    change=service.open_project("P")
    change["name"]="new revision"
    service.store.save("P",change)
    with pytest.raises(ValueError,match="revision conflict"):
        service.restore_view_session("P",receipt["snapshot_id"])
    service.store.close()


def test_e2_real_app_wrong_os_principal_fails_closed(tmp_path):
    ids=SwitchingIdentityProvider(identity("user:A","Alice"))
    service=StructuralProApp(tmp_path/"app",identity_provider=ids)
    service.create_project("project","P")
    receipt=service.save_view_session("P",{"current_tab":"project"})
    ids.identity=identity("user:B","Bob")
    with pytest.raises(PermissionError):
        service.restore_view_session("P",receipt["snapshot_id"])
    with pytest.raises(PermissionError):
        service.save_view_session("P",{"current_tab":"project"})
    service.store.close()
