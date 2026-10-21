"""Bored-pile ownership audit integration: synthetic, never financial approval."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.bored_pile_detail import new_detail
from core.takeoff.bored_pile_ownership_preflight import SCHEMA
from core.takeoff.bored_pile_specialist_chat import compile_piles

ROOT = Path(__file__).resolve().parents[1]


def _json_file(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return {"path": str(path), "sha256": sha256(raw).hexdigest(),
            "reference": "سند صریحاً مصنوعی آزمون"}


def _draft(tmp_path):
    d = new_detail("FND", "PG1")
    e = json.loads((ROOT / "examples/bored_pile_documented_synthetic.json").read_text())
    d["source"] = {"mode": "manual", "source_id": e["source"]["source_id"],
                   "approved_by": e["source"]["approved_by"],
                   "measurement_ref": e["source"]["source_ref"]}
    d["pile_detail"]["input"] = e
    d["pile_detail"]["input_document"] = _json_file(tmp_path / "input.json", e)
    d["pile_detail"]["preflight"] = {
        "reviewer": "IndependentPreview", "ownership_reference_claim": "ممیزی مصنوعی"}
    return d


def _ownership(tmp_path, draft):
    data = draft["pile_detail"]["input"]
    compiled = compile_piles(data)
    pile = data["piles"][0]
    entries = []
    for row in compiled["rows"]:
        pieces = []
        if row["kind"].startswith("rebar_"):
            group = pile["rebars"][row["kind"][6:]]
            series = next(s for s in group["series"]
                          if s["physical_id"] == row["physical_id"])
            pieces = [row["physical_id"] + ":BAR:" + str(i)
                      for i in range(int(series["count"]))]
        entries.append({
            "pile_id": row["pile_id"], "operation": row["kind"],
            "physical_id": row["physical_id"],
            "scope_id": row["physical_id"] + ":scope",
            "payer_kind": "pile", "payer_id": pile["physical_id"],
            "bar_piece_ids": pieces, "evidence_ref": "مدرک مصنوعی هر عملیات",
            "evidence_sha256": draft["pile_detail"]["input_document"]["sha256"],
        })
    document = {
        "schema": SCHEMA, "project_id": data["project_id"],
        "floor_id": data["floor_id"], "group_id": data["group_id"],
        "input_sha256": compiled["source_sha256"],
        "coordinate_ref": data["datum"]["coordinate_ref"],
        "prepared_by": "OwnershipAuthor", "reviewer": "IndependentOwnershipReviewer",
        "allocations": entries,
    }
    draft["pile_detail"]["ownership_document"] = _json_file(tmp_path / "owner.json", document)
    return document


def test_missing_ownership_is_explicitly_blocked_without_losing_engineering(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    app.create_project("مصنوعی", "P")
    draft = _draft(tmp_path)
    app.save_structural_member_draft("P", draft)
    result = app.preview_structural_member("P", "bored_pile", "FND", "PG1")
    assert result["engineering_ready"]
    assert result["ownership_audit"] is None
    assert result["blockers"] and not result["ready"]
    assert not result["commit_allowed"] and result["rows"] == []
    app.store.close()


def test_persisted_independent_owner_evidence_is_audit_only(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    app.create_project("مصنوعی", "P")
    draft = _draft(tmp_path)
    document = _ownership(tmp_path, draft)
    app.save_structural_member_draft("P", draft)
    app.store.close()

    reopened = StructuralProApp(tmp_path / "db")
    result = reopened.preview_structural_member("P", "bored_pile", "FND", "PG1")
    audit = result["ownership_audit"]
    assert audit["status"] == "READ_ONLY_PENDING_CROSS_MEMBER_GATE"
    assert audit["commit_allowed"] is False and audit["ready_for_boq"] is False
    assert len(audit["candidate_owned_rows"]) == 3
    assert result["engineering_ready"] and result["ready"] is False
    assert not result["commit_allowed"] and result["rows"] == []
    assert result["ownership_document_sha256"] == draft["pile_detail"]["ownership_document"]["sha256"]
    assert result["blockers"]
    assert reopened.open_project("P")["boq"] == []
    with pytest.raises(ValueError):
        reopened.commit_structural_member("P", "bored_pile", "FND", "PG1", expected_revision=1)
    assert document["schema"] == SCHEMA
    reopened.store.close()


@pytest.mark.parametrize("tamper", [
    "changed_bytes", "stale_input_hash", "self_review",
    "duplicate_physical_bar", "unknown_piece_count",
])
def test_invalid_ownership_never_removes_payment_gate(tmp_path, tamper):
    from core.takeoff.bored_pile_detail import preview
    draft = _draft(tmp_path)
    owner = _ownership(tmp_path, draft)
    path = Path(draft["pile_detail"]["ownership_document"]["path"])
    if tamper == "changed_bytes":
        path.write_bytes(path.read_bytes() + b"\n")
    elif tamper == "stale_input_hash":
        owner["input_sha256"] = "0" * 64
    elif tamper == "self_review":
        owner["reviewer"] = draft["pile_detail"]["input"]["source"]["approved_by"]
    elif tamper == "duplicate_physical_bar":
        bars = next(r for r in owner["allocations"] if r["bar_piece_ids"])
        bars["bar_piece_ids"][1] = bars["bar_piece_ids"][0]
    elif tamper == "unknown_piece_count":
        bars = next(r for r in owner["allocations"] if r["bar_piece_ids"])
        bars["bar_piece_ids"].pop()
    if tamper != "changed_bytes":
        draft["pile_detail"]["ownership_document"] = _json_file(path, owner)
    result = preview(draft, project_id="P")
    assert result["engineering_ready"]
    assert result["ownership_audit"] is None
    assert not result["ready"] and not result["commit_allowed"] and not result["rows"]
    assert any("مالکیت" in reason for reason in result["blockers"])


def test_unallocated_operations_remain_unknown_not_zero(tmp_path):
    from core.takeoff.bored_pile_detail import preview
    draft = _draft(tmp_path)
    owner = _ownership(tmp_path, draft)
    owner["allocations"].pop()
    draft["pile_detail"]["ownership_document"] = _json_file(
        Path(draft["pile_detail"]["ownership_document"]["path"]), owner)
    result = preview(draft, project_id="P")
    audit = result["ownership_audit"]
    assert audit is not None
    assert audit["excluded_operations"]
    assert all("quantity" not in item for item in audit["excluded_operations"])
    assert not result["ready"] and not result["rows"] and not result["commit_allowed"]
