"""Real IFC4 + canonical project SQLite tests for explicit nonfinancial lineage."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from test_phase2_priority5_closure import identity_case


def _review(app, source, *, revision, gid, member, proof, supersedes=None):
    doc = sha256(source.read_bytes()).hexdigest()
    proposal = app.save_ifc_identity_proposal(
        "P", str(source), revision=revision, global_id=gid,
        floor_id="F1", member_id=member, author="author",
        reference="Explicit synthetic member ownership", source_sha256=doc,
        expected_digest=app.store.current_digest("P"),
    )
    args = dict(
        proposal_id=proposal["id"], reviewer="reviewer",
        evidence_path=str(proof), evidence_sha256=sha256(proof.read_bytes()).hexdigest(),
        note="Independent registered application reviewer; synthetic",
        expected_digest=app.store.current_digest("P"),
    )
    app.review_ifc_identity("P", **args, supersedes=supersedes)
    return proposal["id"]


def _case(tmp_path, mode="split"):
    import ifcopenshell as ifc

    app, old_path, proof, first, args = identity_case(tmp_path)
    app.review_ifc_identity("P", **args)
    old_ids = [first["id"]]
    if mode == "merge":
        app.add_project_member("P", "B2", "F1", "beam")
        old_model = ifc.open(str(old_path))
        old_ids.append(_review(
            app, old_path, revision="R1",
            gid=old_model.by_type("IfcColumn")[0].GlobalId,
            member="B2", proof=proof,
        ))
        app.add_project_member("P", "B3", "F1", "beam")
        current_members = ["B3"]
    else:
        app.add_project_member("P", "B2", "F1", "beam")
        app.add_project_member("P", "B3", "F1", "beam")
        current_members = ["B2", "B3"]

    model = ifc.open(str(old_path))
    beam = model.by_type("IfcBeam")[0]
    beam.GlobalId = ifc.guid.new()
    targets = [beam]
    if mode == "split":
        column = model.by_type("IfcColumn")[0]
        column.GlobalId = ifc.guid.new()
        targets.append(column)
    new_path = tmp_path / "R2.ifc"
    model.write(str(new_path))
    current_ids = [
        _review(app, new_path, revision="R2",
                gid=obj.GlobalId, member=member, proof=proof)
        for obj, member in zip(targets, current_members)
    ]
    edges = (
        [{"previous_proposal_id": old_ids[0],
          "current_proposal_id": current,
          "physical_scope_reference": "test-fixture/explicit-face-" + str(n)}
         for n, current in enumerate(current_ids)]
        if mode == "split" else
        [{"previous_proposal_id": old,
          "current_proposal_id": current_ids[0],
          "physical_scope_reference": "test-fixture/explicit-face-" + str(n)}
         for n, old in enumerate(old_ids)]
    )
    data = {
        "policy": "reviewed_ifc_lineage_v1", "project_id": "P", "mode": mode,
        "previous_proposal_ids": old_ids,
        "current_proposal_ids": current_ids,
        "previous_source_sha256": sha256(old_path.read_bytes()).hexdigest(),
        "current_source_sha256": sha256(new_path.read_bytes()).hexdigest(),
        "edges": edges,
    }
    evidence = tmp_path / "lineage.json"
    evidence.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
    args = {
        "mode": mode, "previous_proposal_ids": old_ids,
        "current_proposal_ids": current_ids,
        "author": "author", "reviewer": "reviewer",
        "evidence_path": str(evidence), "evidence_sha256": sha256(evidence.read_bytes()).hexdigest(),
        "note": "Explicit synthetic source/target trace, without quantity allocation",
        "expected_digest": app.store.current_digest("P"),
    }
    return app, args, evidence, data


@pytest.mark.parametrize("mode", ["split", "merge"])
def test_lineage_review_is_append_only_nonfinancial_and_reopen_safe(tmp_path, mode):
    from core.drawings.ifc_pipeline import quantity_formula_data
    from core.platform.application import StructuralProApp

    app, args, _, _ = _case(tmp_path, mode)
    reviewed = app.review_ifc_identity_lineage("P", **args)
    assert reviewed["status"] == "reviewed_nonfinancial"
    assert reviewed["ready"] is False and reviewed["commit_allowed"] is False
    assert reviewed["engineering_accepted"] is False and reviewed["payable_rows"] == []
    assert reviewed["mode"] == mode
    assert app.open_project("P")["boq"] == []
    for pid in args["previous_proposal_ids"] + args["current_proposal_ids"]:
        with pytest.raises(ValueError,match="Split/Merge"):
            quantity_formula_data(app,"P",pid,"Length",author="author")
    current = app.open_project("P")
    before = app.store.current_digest("P")
    tampered = deepcopy(current)
    tampered["ifc_identity_lineages"][0]["mode"] = "fake"
    with pytest.raises(ValueError,match="تاریخچه"):
        app.store.save("P",tampered,expected_digest=before)
    assert app.store.current_digest("P") == before
    app.store.close()
    reopened = StructuralProApp(tmp_path/"app")
    assert reopened.open_project("P")["ifc_identity_lineages"] == [reviewed]
    assert reopened.store.integrity_check()["ok"]
    assert reopened.open_project("P")["takeoffs"] == []
    reopened.store.close()


@pytest.mark.parametrize("mutation", [
    "duplicate_old", "bad_mode", "wrong_source", "missing_edge",
    "duplicate_edge", "wrong_edge", "empty_scope", "modified_proof",
    "wrong_reviewer", "same_reviewer", "stale_revision", "changed_owner",
])
def test_lineage_rejects_bad_evidence_or_owner_without_sqlite_write(tmp_path, mutation):
    app, args, evidence, data = _case(tmp_path)
    args=deepcopy(args)
    if mutation == "duplicate_old":
        args["previous_proposal_ids"] *= 2
    elif mutation == "bad_mode":
        args["mode"]="other"
    elif mutation == "wrong_source":
        data["current_source_sha256"] = "0"*64
    elif mutation == "missing_edge":
        data["edges"].pop()
    elif mutation == "duplicate_edge":
        data["edges"][1] = deepcopy(data["edges"][0])
    elif mutation == "wrong_edge":
        data["edges"][0]["previous_proposal_id"] = "unknown"
    elif mutation == "empty_scope":
        data["edges"][0]["physical_scope_reference"] = ""
    elif mutation == "modified_proof":
        evidence.write_text("changed",encoding="utf-8")
    elif mutation == "wrong_reviewer":
        args["reviewer"] = "no-such-user"
    elif mutation == "same_reviewer":
        args["reviewer"] = "author"
    elif mutation == "stale_revision":
        app.add_project_floor("P","new",level="F2")
    elif mutation == "changed_owner":
        # Verify a corrupted ownership snapshot without writing bad source to SQLite.
        from core.drawings.ifc_lineage import validate_lineage
        bad_project=deepcopy(app.open_project("P"))
        bad_project["members"][1]["floor_id"]="F999"
        before=app.store.current_digest("P")
        with pytest.raises(ValueError):
            validate_lineage(
                bad_project, mode="split",
                previous_proposal_ids=args["previous_proposal_ids"],
                current_proposal_ids=args["current_proposal_ids"], evidence=data)
        assert app.store.current_digest("P")==before
        app.store.close()
        return
    if mutation in {"wrong_source","missing_edge","duplicate_edge","wrong_edge","empty_scope"}:
        evidence.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
        args["evidence_sha256"] = sha256(evidence.read_bytes()).hexdigest()
    before=app.store.current_digest("P")
    with pytest.raises((ValueError,PermissionError,RuntimeError)):
        app.review_ifc_identity_lineage("P",**args)
    assert app.store.current_digest("P")==before
    assert app.open_project("P").get("ifc_identity_lineages",[])==[]
    assert app.open_project("P")["boq"]==[]
    app.store.close()


def test_lineage_cannot_be_reapplied_or_forged_with_direct_sqlite_command(tmp_path):
    from core.drawings.ifc_lineage import lineage_guard
    app,args,evidence,_ = _case(tmp_path)
    reviewed=app.review_ifc_identity_lineage("P",**args)
    args["expected_digest"]=app.store.current_digest("P")
    before=app.store.current_digest("P")
    with pytest.raises(ValueError):
        app.review_ifc_identity_lineage("P",**args)
    assert app.store.current_digest("P")==before
    p=deepcopy(app.open_project("P"))
    fake={**reviewed,"id":"fake-id","status":"approved","commit_allowed":True}
    p["ifc_identity_lineages"].append(fake)
    with pytest.raises(ValueError):
        app.store.save("P",p,expected_digest=before,
                       ifc_command={"action":"review_lineage","record":fake})
    assert app.store.current_digest("P")==before
    app.store.close()


@pytest.mark.parametrize("mode", ["split", "merge"])
def test_lineage_blocks_linked_cad_and_manual_member_boq_claims(tmp_path, mode):
    from core.takeoff.commit_guards import validate_commit_rows

    app, args, _, _ = _case(tmp_path, mode)
    app.review_ifc_identity_lineage("P", **args)
    project=app.open_project("P")
    target="B2" if mode == "split" else "B3"
    before=app.store.current_digest("P")
    # A distinct CAD source id cannot conceal the unresolved physical owner.
    row={
        "id":"CAD-NEW","source_id":"independent-cad-session",
        "member_code":target,"system":"F1",
        "params":{"cad_evidence":{"floor_id":"F1","member_id":target}},
        "quantities":[{"unit":"m","amount":"4","code":"Q","title":"طول"}],
    }
    with pytest.raises(ValueError,match="Split/Merge"):
        validate_commit_rows(project,[row],source_id=row["source_id"])
    assert app.store.current_digest("P")==before
    assert app.open_project("P")["boq"]==[]
    app.store.close()
