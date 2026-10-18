"""Read-only joint ownership regression against real StructuralProApp/SQLite.

Reconstructed independently from the persisted joint contract; this is not a
byte-for-byte replay of Work's unpublished local commit. Synthetic evidence
never constitutes engineering acceptance or authority to populate the BOQ.
"""
from copy import deepcopy
from hashlib import sha256

import pytest

from app.bored_pile_draft_controller import PileDraftController
from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_joint_crosswalk import (
    POLICY, OwnershipError, _digest, audit_joint_contract,
)
from core.takeoff.bored_pile_specialist_chat import compile_piles

from test_bored_pile_real_application_controller import (
    _document, _ownership, _setup,
)


GEOMETRY_SHA = sha256(b"synthetic-target-geometry").hexdigest()


def _saved_joint_case(tmp_path):
    """Use the production persistence API; do not forge an accepted takeoff."""
    app, controller, data = _setup(tmp_path)
    owner = _ownership(data)
    controller.attach_ownership(
        _document(tmp_path / "owner-joint.json", owner),
        reference="Synthetic identity schedule",
    )
    controller.save()

    cap = app.new_structural_member("pile_cap", "FND", "CAP1")
    cap["source"] = {
        "mode": "manual", "source_id": "CAP-SRC-1",
        "approved_by": "CapAuthor", "measurement_ref": "CapDrawing",
    }
    # Explicit gap between the cap lower elevation (-1.0) and pile top
    # (-1.25). Neither horizontal overlap nor a deduction is inferred.
    cap["geometry"] = {
        "physical_cap_id": "CAP-PH-1",
        "top_elevation_m": "0", "bottom_elevation_m": "-1.0",
        "source_ref": "CapDocument", "source_sha256": GEOMETRY_SHA,
    }
    app.save_structural_member_draft("P", cap)
    app.store.close()

    reopened = StructuralProApp(tmp_path / "db")
    current = PileDraftController(reopened, "P")
    current.load("FND", "PG1")
    project = reopened.open_project("P")
    targets = [record for record in project["reviewed_structural_members"].values()
               if record["data"].get("kind") == "pile_cap" and
               record["data"].get("member_id") == "CAP1"]
    assert len(targets) == 1
    cap_record = targets[0]
    compiled = compile_piles(data)
    assert current.data["pile_detail"]["ownership_document"]["sha256"]
    joint = {
        "policy": POLICY, "project_id": "P", "floor_id": "FND",
        "group_id": "PG1", "input_sha256": compiled["source_sha256"],
        "ownership_sha256": current.data["pile_detail"]["ownership_document"]["sha256"],
        "coordinate_ref": data["datum"]["coordinate_ref"],
        "vertical_datum_ref": data["datum"]["vertical_datum_ref"],
        "prepared_by": "JointAuthor", "reviewer": "JointIndependentReviewer",
        "interfaces": [{
            "pile_id": data["piles"][0]["id"], "other_kind": "pile_cap",
            "other_floor_id": "FND", "other_member_id": "CAP1",
            "other_physical_id": "CAP-PH-1",
            "other_record_sha256": _digest(cap_record),
            "other_revision": cap_record["revision"],
            "geometry_reference": "CapDocument", "geometry_sha256": GEOMETRY_SHA,
            "spatial_status": "documented_no_overlap",
            "pile_top_m": data["piles"][0]["top_elevation_m"],
            "pile_bottom_m": data["piles"][0]["bottom_elevation_m"],
            "other_top_m": "0", "other_bottom_m": "-1.0",
            "overlap_volume_m3": "0", "deduction_id": "none",
            "allocation_owner": "not_applicable",
        }],
        "bar_transfers": [],  # Starter group explicitly not applicable.
    }
    return reopened, current, data, compiled, owner, joint, project


def _audit(case, *, joint=None, snapshot=None):
    app, controller, data, compiled, owner, original_joint, project = case
    document = joint if joint is not None else original_joint
    snapshot = snapshot if snapshot is not None else project
    return audit_joint_contract(
        data, compiled, owner,
        controller.data["pile_detail"]["ownership_document"]["sha256"],
        document, snapshot,
    )


def test_actual_sqlite_roundtrip_joint_audit_never_unlocks_financials(tmp_path):
    case = _saved_joint_case(tmp_path)
    app, controller, data, compiled, owner, joint, snapshot = case
    try:
        result = _audit(case)
        assert result["status"] == "JOINT_CROSSWALK_PREVIEW_ONLY"
        assert len(result["matched_interfaces"]) == 1
        assert result["matched_starter_pieces"] == 0
        assert result["ready_for_boq"] is False
        assert result["commit_allowed"] is False and result["rows"] == []
        preview = controller.preview()
        assert preview["engineering_ready"] and not preview["ready"]
        assert not preview["commit_allowed"] and preview["rows"] == []
        with pytest.raises(ValueError):
            app.commit_structural_member("P", "bored_pile", "FND", "PG1",
                                         expected_revision=controller.revision)
        project_after = app.open_project("P")
        assert project_after["boq"] == snapshot["boq"] == []
        assert project_after["takeoffs"] == snapshot["takeoffs"] == []
        assert app.store.db.execute("pragma integrity_check").fetchone()[0] == "ok"
    finally:
        app.store.close()


@pytest.mark.parametrize("change", ["revision", "record_digest", "geometry", "target_id", "payer"])
def test_real_snapshot_rejects_stale_or_ambiguous_joint_claim(tmp_path, change):
    case = _saved_joint_case(tmp_path)
    app, controller, data, compiled, owner, joint, snapshot = case
    candidate = deepcopy(joint)
    modified_snapshot = deepcopy(snapshot)
    try:
        link = candidate["interfaces"][0]
        if change == "revision":
            link["other_revision"] += 1
        elif change == "record_digest":
            link["other_record_sha256"] = "f" * 64
        elif change == "geometry":
            link["other_top_m"] = "-2"
        elif change == "target_id":
            link["other_physical_id"] = "another-cap"
        else:
            link["allocation_owner"] = "other_member"
        with pytest.raises(OwnershipError):
            _audit(case, joint=candidate, snapshot=modified_snapshot)
        assert app.open_project("P")["boq"] == []
        assert app.open_project("P")["takeoffs"] == []
    finally:
        app.store.close()


def test_changed_signed_owner_document_is_invalidated_after_reopen(tmp_path):
    case = _saved_joint_case(tmp_path)
    app, controller, data, compiled, owner, joint, snapshot = case
    try:
        owner_path = controller.data["pile_detail"]["ownership_document"]["path"]
        with open(owner_path, "ab") as stream:
            stream.write(b"\n")
        preview = controller.preview()
        assert preview["engineering_ready"]
        assert preview["ownership_audit"] is None
        assert not preview["ready"] and not preview["commit_allowed"]
        assert preview["rows"] == []
        assert app.open_project("P")["boq"] == []
    finally:
        app.store.close()
