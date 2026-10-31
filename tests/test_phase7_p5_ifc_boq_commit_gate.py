"""P7 E8 final: reviewed IFC/CAD ownership is mandatory in actual BOQ commits.

All positive artifacts use real persisted SQLite+IFC+DXF; test authors and
reviewers are explicitly independent. No automatic IFC quantity claims.
"""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from test_phase2_priority5_closure import crosswalk_case
from core.reports.ifc_crosswalk_source_audit import require_reviewed_ifc_crosswalks_for_boq


def _linked(tmp_path):
    app, model, drawing, session, proposal, kw = crosswalk_case(tmp_path)
    first = app.save_ifc_crosswalk("P", **kw)
    project = app.open_project("P")
    options = dict(
        project_id="P", expected_project_version=project["_meta"]["version"],
        session_id=kw["session_id"], selected_item_ids=(kw["item_id"],),
    )
    return app, model, drawing, first, kw, project, options


def test_reviewed_ifc_cad_links_real_boq_commit_without_second_quantity(tmp_path):
    app, model, drawing, crosswalk, kw, project, options = _linked(tmp_path)
    try:
        preflight = require_reviewed_ifc_crosswalks_for_boq(app, **options)
        assert preflight["scope"] == "REVIEWED_IFC_CROSSWALK_SOURCE_PREFLIGHT_ONLY"
        assert preflight["verified_crosswalk_ids"] == [crosswalk["id"]]
        assert not preflight["commit_authority"] and not preflight["payable_rows"]
        assert app.open_project("P") == project
        committed = app.commit_drawing_takeoff_to_boq(
            "P", kw["session_id"], [kw["item_id"]], expected_session_revision=1,
        )
        result = app.open_project("P")
        assert len(result["takeoffs"]) == 1
        assert len(result["boq"]) >= 1
        assert committed["takeoffs_added"][0]["source_id"] in {
            s for row in result["boq"] for s in row["source_ids"]
        }
        assert len(result["ifc_2d_crosswalks"]) == 1
    finally:
        app.store.close()


@pytest.mark.parametrize("which", ["ifc", "drawing", "evidence"])
def test_real_boq_commit_rejects_replaced_ifc_cad_review_documents_without_write(tmp_path, which):
    app, model, drawing, crosswalk, kw, project, options = _linked(tmp_path)
    from pathlib import Path
    evidence = Path(kw["evidence_path"])
    path = {"ifc": model, "drawing": drawing, "evidence": evidence}[which]
    before = app.store.current_digest("P")
    try:
        path.write_bytes(path.read_bytes() + b"modified-after-independent-review")
        with pytest.raises((ValueError, RuntimeError)):
            app.commit_drawing_takeoff_to_boq(
                "P", kw["session_id"], [kw["item_id"]], expected_session_revision=1,
            )
        assert app.store.current_digest("P") == before
        assert app.open_project("P") == project
    finally:
        app.store.close()


def test_actual_reviewed_crosswalk_reviewer_revocation_blocks_commit(tmp_path):
    from core.collaboration.workspace import User
    app, model, drawing, crosswalk, kw, project, options = _linked(tmp_path)
    before = app.store.current_digest("P")
    try:
        app.collaboration.users["reviewer"] = User("reviewer", "بازبین", "viewer")
        with pytest.raises(PermissionError):
            app.commit_drawing_takeoff_to_boq(
                "P", kw["session_id"], [kw["item_id"]], expected_session_revision=1,
            )
        assert app.store.current_digest("P") == before
        assert app.open_project("P") == project
    finally:
        app.store.close()


def test_two_independently_reviewed_crosswalks_on_same_owner_need_independent_resolution(tmp_path):
    from core.drawings.takeoff_session import DrawingTakeoffSession
    from core.drawings.dwg_takeoff import DWGTakeoffEngine

    app, model, drawing, first, kw, project, options = _linked(tmp_path)
    try:
        doc = DWGTakeoffEngine.with_array_support().import_file(drawing)
        handle = first["drawing"]["handle"]
        extra = DrawingTakeoffSession(str(drawing))
        item = extra.add_cad_entity(doc, handle, "length", takeoff_code="TEST",
                                    floor_id="F1", member_id="B1",
                                    quantity_owner="B1", created_by="author",
                                    reference="second independently recorded 2D receipt")
        extra.review_cad_entity(item.id, reviewer="reviewer",
                                note="independent second drawing source review")
        saved = app.save_drawing_takeoff_session("P", extra)
        proof = json.loads(open(kw["evidence_path"], encoding="utf-8").read())
        proof.update(session_id=saved["session_id"], item_id=item.id)
        p = tmp_path / "crosswalk-second.json"
        p.write_text(json.dumps(proof), encoding="utf-8")
        app.save_ifc_crosswalk(
            "P", proposal_id=first["proposal_id"],
            session_id=saved["session_id"], item_id=item.id,
            author="author", reviewer="reviewer",
            evidence_path=str(p), evidence_sha256=sha256(p.read_bytes()).hexdigest(),
            expected_digest=app.store.current_digest("P"),
        )
        snapshot = app.open_project("P")
        arguments = dict(options, expected_project_version=snapshot["_meta"]["version"])
        digest = app.store.current_digest("P")
        with pytest.raises(ValueError, match="Crosswalk"):
            require_reviewed_ifc_crosswalks_for_boq(app, **arguments)
        with pytest.raises(ValueError):
            app.commit_drawing_takeoff_to_boq(
                "P", kw["session_id"], [kw["item_id"]], expected_session_revision=1,
            )
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == snapshot
    finally:
        app.store.close()
