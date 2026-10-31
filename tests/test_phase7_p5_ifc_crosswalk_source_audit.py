"""P7 P5: independently approved real IFC+DXF crosswalks from SQLite."""
from copy import deepcopy
from hashlib import sha256
import pytest

from test_phase2_priority5_closure import crosswalk_case
from core.reports.ifc_crosswalk_source_audit import inspect_reviewed_ifc_crosswalks


def _case(tmp_path):
    service, model, drawing, session, proposal, kwargs = crosswalk_case(tmp_path)
    crosswalk = service.save_ifc_crosswalk("P", **kwargs)
    current = service.open_project("P")
    query = {
        "project_id": "P",
        "expected_project_version": current["_meta"]["version"],
        "selected_crosswalk_ids": (crosswalk["id"],),
    }
    return service, model, drawing, kwargs, crosswalk, current, query


def test_real_reviewed_ifc_cad_source_and_sqlite_are_verified_without_quantity(tmp_path):
    app, model, drawing, opts, crosswalk, project, args = _case(tmp_path)
    digest = app.store.current_digest("P")
    try:
        report = inspect_reviewed_ifc_crosswalks(app, **args)
        assert report["status"] == "VERIFIED_SOURCE_REFERENCES_ONLY"
        assert len(report["crosswalks"]) == 1
        proof = report["crosswalks"][0]
        assert proof["member_id"] == "B1"
        assert proof["floor_id"] == "F1"
        assert proof["ifc_global_id"] == crosswalk["global_id"]
        assert proof["drawing_source_sha256"] == sha256(drawing.read_bytes()).hexdigest()
        assert proof["ifc_source_sha256"] == sha256(model.read_bytes()).hexdigest()
        assert report["quantity_inferred"] is False
        assert report["commit_allowed"] is False
        assert report["payable_rows"] == []
        assert report["engineering_accepted"] is False
        assert report["readonly"] is True
        assert report["multiple_physical_claims"] == []
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == project
    finally:
        app.store.close()


@pytest.mark.parametrize("target", ["model", "drawing", "proof"])
def test_changed_primary_ifc_dxf_or_review_evidence_fail_closed(tmp_path, target):
    app, model, drawing, opts, crosswalk, project, args = _case(tmp_path)
    before = app.store.current_digest("P")
    try:
        path = {"model": model, "drawing": drawing,
                "proof": __import__("pathlib").Path(opts["evidence_path"])}[target]
        path.write_bytes(path.read_bytes() + b"changed-after-independent-review")
        with pytest.raises((ValueError, RuntimeError)):
            inspect_reviewed_ifc_crosswalks(app, **args)
        assert app.store.current_digest("P") == before
        assert app.open_project("P") == project
    finally:
        app.store.close()


@pytest.mark.parametrize("invalid", ["old_version", "unknown", "duplicate", "bool_version"])
def test_invalid_version_or_unregistered_or_duplicate_crosswalk_rejected(tmp_path, invalid):
    app, model, drawing, opts, crosswalk, project, args = _case(tmp_path)
    try:
        if invalid == "old_version":
            args["expected_project_version"] -= 1
        elif invalid == "unknown":
            args["selected_crosswalk_ids"] = ("fake-crosswalk",)
        elif invalid == "duplicate":
            args["selected_crosswalk_ids"] *= 2
        else:
            args["expected_project_version"] = True
        with pytest.raises(ValueError):
            inspect_reviewed_ifc_crosswalks(app, **args)
    finally:
        app.store.close()


def test_forged_reviewed_member_does_not_create_ifc_ownership_or_payment(tmp_path, monkeypatch):
    app, model, drawing, opts, crosswalk, project, args = _case(tmp_path)
    original = app.open_project
    try:
        def forged(pid):
            altered = deepcopy(original(pid))
            altered["ifc_2d_crosswalks"][0]["member_id"] = "UNREVIEWED-MEMBER"
            return altered
        monkeypatch.setattr(app, "open_project", forged)
        with pytest.raises(ValueError):
            inspect_reviewed_ifc_crosswalks(app, **args)
    finally:
        app.store.close()


def test_reviewer_role_revoked_blocks_reuse_of_old_approved_crosswalk(tmp_path):
    from core.collaboration.workspace import User
    app, model, drawing, opts, crosswalk, project, args = _case(tmp_path)
    try:
        app.collaboration.add_user(User("reviewer", "بازبین", "viewer"))
        with pytest.raises(PermissionError):
            inspect_reviewed_ifc_crosswalks(app, **args)
    finally:
        app.store.close()
