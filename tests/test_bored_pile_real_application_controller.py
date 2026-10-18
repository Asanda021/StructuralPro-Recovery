"""Real StructuralProApp / SQLite / CAS acceptance for bored-pile draft controls.

Runs against the checked-out repository, not a mocked service. Synthetic
evidence only; a PASS never licenses a payment or engineering design.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

import pytest

from app.bored_pile_draft_controller import PileDraftController
from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_specialist_chat import compile_piles

ROOT = Path(__file__).resolve().parents[1]


def _document(path, data):
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    path.write_bytes(raw)
    return str(path)


def _setup(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    app.create_project("پروژه مصنوعی شمع", "P")
    controller = PileDraftController(app, "P")
    controller.new("FND", "PG1")
    data = json.loads((ROOT / "examples/bored_pile_documented_synthetic.json").read_text(encoding="utf-8"))
    src = {"mode": "manual", "source_id": data["source"]["source_id"],
           "approved_by": data["source"]["approved_by"],
           "measurement_ref": data["source"]["source_ref"]}
    docpath = _document(tmp_path / "pile.json", data)
    controller.attach_input(docpath, source=src)
    controller.set_preflight(reviewer="IndependentPreview",
                             ownership_reference="Synthetic ownership audit only")
    return app, controller, data


def _ownership(data):
    compiled = compile_piles(data)
    piles = {p["id"]:p for p in data["piles"]}
    allocations = []
    for row in compiled["rows"]:
        pile = piles[row["pile_id"]]
        pieces = []
        if row["kind"].startswith("rebar_"):
            group = pile["rebars"][row["kind"][len("rebar_"):]]
            series = next(s for s in group["series"] if s["physical_id"] == row["physical_id"])
            pieces = [row["physical_id"] + "::" + str(n)
                      for n in range(int(series["count"]))]
        allocations.append({
            "pile_id":row["pile_id"], "operation":row["kind"],
            "physical_id":row["physical_id"], "scope_id":row["physical_id"]+"::scope",
            "payer_kind":"pile", "payer_id":pile["physical_id"],
            "bar_piece_ids":pieces, "evidence_ref":"synthetic reference",
            "evidence_sha256":compiled["source_sha256"],
        })
    return {
        "schema":"bored_pile_ownership_preflight_v1",
        "project_id":data["project_id"], "floor_id":data["floor_id"],
        "group_id":data["group_id"], "input_sha256":compiled["source_sha256"],
        "coordinate_ref":data["datum"]["coordinate_ref"],
        "prepared_by":"OwnerPreparer", "reviewer":"IndependentOwnershipReviewer",
        "allocations":allocations,
    }


def test_actual_application_sqlite_evidence_and_blocked_boq(tmp_path):
    app, controller, data = _setup(tmp_path)
    owner = _ownership(data)
    assert not controller.attach_ownership(
        _document(tmp_path / "owner.json", owner), reference="Synthetic owner contract"
    )["ready_for_boq"]
    assert controller.dirty
    before = controller.preview()
    assert before["engineering_ready"]
    assert before["ownership_audit"] is not None
    assert before["ready"] is False and before["commit_allowed"] is False and before["rows"] == []
    controller.save()
    assert controller.revision == 1 and not controller.dirty
    assert app.store.db.execute("pragma integrity_check").fetchone()[0] == "ok"
    app.store.close()

    other = StructuralProApp(tmp_path / "db")
    loaded = PileDraftController(other, "P")
    loaded.load("FND", "PG1")
    assert loaded.revision == 1 and loaded.data["pile_detail"]["input"] == data
    assert loaded.preview()["ownership_audit"] is not None
    project = other.open_project("P")
    assert project["takeoffs"] == [] and project["boq"] == []
    with pytest.raises(ValueError):
        other.commit_structural_member("P", "bored_pile", "FND", "PG1", expected_revision=1)
    assert other.open_project("P")["boq"] == []
    other.store.close()


def test_actual_application_cas_conflict_preserves_committed_draft(tmp_path):
    app, controller, _ = _setup(tmp_path)
    controller.save()
    peer = StructuralProApp(tmp_path / "db")
    second = PileDraftController(peer, "P")
    second.load("FND", "PG1")
    controller.set_preflight(reviewer="ReviewerV2", ownership_reference="New audit")
    controller.save()
    assert controller.revision == 2
    second.set_preflight(reviewer="ReviewerStale", ownership_reference="Stale")
    with pytest.raises(RuntimeError):
        second.save()
    assert second.dirty and second.revision == 1
    current = PileDraftController(peer, "P")
    current.load("FND", "PG1")
    assert current.revision == 2
    assert current.data["pile_detail"]["preflight"]["reviewer"] == "ReviewerV2"
    assert peer.open_project("P")["boq"] == []
    peer.store.close()
    app.store.close()


def test_changed_evidence_fails_read_only_preflight_after_persistence(tmp_path):
    app, controller, data = _setup(tmp_path)
    controller.attach_ownership(
        _document(tmp_path / "owner.json", _ownership(data)),reference="Synthetic reference")
    controller.save()
    owner_path = Path(controller.data["pile_detail"]["ownership_document"]["path"])
    owner_path.write_bytes(owner_path.read_bytes()+b"\n")
    result = controller.preview()
    assert result["engineering_ready"] is True
    assert result["ownership_audit"] is None
    assert result["ready"] is False and result["commit_allowed"] is False
    assert any("مالکیت" in reason for reason in result["blockers"])
    assert app.open_project("P")["boq"] == []
    app.store.close()
