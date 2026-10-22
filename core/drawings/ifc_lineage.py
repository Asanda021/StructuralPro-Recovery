"""Explicit, append-only IFC split/merge lineage. Identity review is NOT BOQ approval.

The prior and current identities must already be independently reviewed through
the canonical IFC identity service. No quantities, percentages or material amounts
are inferred from a graph edge or the model geometry.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


def _ids(values, label):
    if not isinstance(values, list) or not values or any(
        not isinstance(v, str) or not v.strip() or v != v.strip() for v in values
    ):
        raise ValueError(f"شناسه‌های {label} IFC باید صریح و معتبر باشند")
    if len(values) != len(set(values)):
        raise ValueError(f"شناسه تکراری در {label} IFC")
    return values


def _reviewed_sets(project, old_ids, new_ids, mode):
    from core.drawings.ifc_pipeline import _binding
    from core.projects.project_model import _identity

    _ids(old_ids, "اعضای قبلی")
    _ids(new_ids, "اعضای جدید")
    if mode not in ("split", "merge"):
        raise ValueError("نوع تغییر IFC فقط Split یا Merge است")
    if mode == "split" and (len(old_ids) != 1 or len(new_ids) < 2):
        raise ValueError("Split باید از یک عضو به دست‌کم دو عضو مستند باشد")
    if mode == "merge" and (len(old_ids) < 2 or len(new_ids) != 1):
        raise ValueError("Merge باید از دست‌کم دو عضو به یک عضو مستند باشد")
    if set(old_ids) & set(new_ids):
        raise ValueError("تطبیق قبلی و جدید IFC نمی‌توانند یک رکورد باشند")

    old = [_binding(project, x)[0] for x in old_ids]
    new = [_binding(project, x)[0] for x in new_ids]
    all_records = old + new
    if any(r.get("status") != "approved" or r.get("commit_allowed") is not False
           or r.get("payable_rows") != [] for r in all_records):
        raise ValueError("تطبیق‌های IFC هنوز بازبینی مجاز غیرمالی ندارند")
    if any(_identity(r.get("project_id")) != _identity(project.get("id"))
           for r in all_records):
        raise ValueError("هویت پروژه IFC با بازبینی تطابق ندارد")
    buildings = {_identity(r["building_id"]) for r in all_records}
    if len(buildings) != 1:
        raise ValueError("تغییر ساختمان IFC بدون مدرک هویت مجاز نیست")
    old_sources = {r["document"]["source_sha256"] for r in old}
    new_sources = {r["document"]["source_sha256"] for r in new}
    old_revisions = {r["document"]["revision"] for r in old}
    new_revisions = {r["document"]["revision"] for r in new}
    if len(old_sources) != 1 or len(new_sources) != 1 or old_sources == new_sources:
        raise ValueError("Split/Merge به دو منبع IFC نسخه‌دار متفاوت نیاز دارد")
    if len(old_revisions) != 1 or len(new_revisions) != 1 or old_revisions == new_revisions:
        raise ValueError("Revision قبلی و جدید IFC باید صریح و متفاوت باشند")

    def owners(items):
        values = [(_identity(r["floor_id"]), _identity(r["member_id"])) for r in items]
        if len(values) != len(set(values)):
            raise ValueError("یک مالک فیزیکی IFC چند بار در یک Revision به کار رفته است")
        return set(values)

    if owners(old) & owners(new):
        raise ValueError("مالکیت قدیم و جدید در Split/Merge مبهم است؛ تغییر عضو صریح لازم است")
    for prior in project.get("ifc_identity_lineages", []):
        if set(prior["previous_proposal_ids"]) & set(old_ids):
            raise ValueError("تطبیق قبلی IFC پیش‌تر در Split/Merge مصرف شده است")
        if set(prior["current_proposal_ids"]) & set(new_ids):
            raise ValueError("تطبیق جدید IFC پیش‌تر در Split/Merge ثبت شده است")
    return old, new


def _check_edges(proof, old_ids, new_ids, mode):
    edges = proof.get("edges")
    if not isinstance(edges, list):
        raise ValueError("جدول پیوند فیزیکی Split/Merge لازم است")
    expected = (
        {(old_ids[0], child) for child in new_ids}
        if mode == "split" else
        {(parent, new_ids[0]) for parent in old_ids}
    )
    actual = set()
    if len(edges) != len(expected):
        raise ValueError("جدول پیوند IFC همه اعضا را دقیقاً پوشش نمی‌دهد")
    for edge in edges:
        if not isinstance(edge, dict) or set(edge) != {
            "previous_proposal_id", "current_proposal_id", "physical_scope_reference"
        }:
            raise ValueError("هر پیوند IFC باید دو شناسه و مرجع محدوده فیزیکی داشته باشد")
        pair = (edge["previous_proposal_id"], edge["current_proposal_id"])
        reference = edge["physical_scope_reference"]
        if (not all(isinstance(x, str) for x in pair)
                or not isinstance(reference, str) or not reference.strip()
                or pair in actual):
            raise ValueError("پیوند فیزیکی IFC خالی یا تکراری است")
        actual.add(pair)
    if actual != expected:
        raise ValueError("گراف Split/Merge با اعضای مستند تطبیق ندارد")


def validate_lineage(project, *, mode, previous_proposal_ids,
                     current_proposal_ids, evidence):
    """Validate authoritative identity and edge topology, never quantities."""
    old, new = _reviewed_sets(project, previous_proposal_ids, current_proposal_ids, mode)
    if not isinstance(evidence, dict):
        raise ValueError("مدرک تغییر هویت IFC معتبر نیست")
    expected = {
        "policy": "reviewed_ifc_lineage_v1",
        "project_id": str(project["id"]),
        "mode": mode,
        "previous_proposal_ids": previous_proposal_ids,
        "current_proposal_ids": current_proposal_ids,
        "previous_source_sha256": old[0]["document"]["source_sha256"],
        "current_source_sha256": new[0]["document"]["source_sha256"],
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise ValueError("مدرک Split/Merge با نسخه‌ها و هویت‌های اصلی مطابقت ندارد")
    _check_edges(evidence, previous_proposal_ids, current_proposal_ids, mode)
    return {
        "mode": mode,
        "previous_proposal_ids": list(previous_proposal_ids),
        "current_proposal_ids": list(current_proposal_ids),
        "previous_source_sha256": expected["previous_source_sha256"],
        "current_source_sha256": expected["current_source_sha256"],
        "edges": deepcopy(evidence["edges"]),
        "ready": False,
        "commit_allowed": False,
        "payable_rows": [],
        "engineering_accepted": False,
    }


def lineage_guard(previous, updated, command):
    """SQLite boundary: lineage history is append-only and command-scoped."""
    old = previous.get("ifc_identity_lineages", [])
    new = updated.get("ifc_identity_lineages", [])
    if not isinstance(old, list) or not isinstance(new, list):
        raise ValueError("دفتر تاریخچه تغییر هویت IFC نامعتبر است")
    if old == new:
        return
    if (new[:len(old)] != old or len(new) != len(old) + 1
            or not isinstance(new[-1], dict)):
        raise ValueError("تاریخچه Split/Merge IFC قابل بازنویسی نیست")
    event = new[-1]
    if not command or command.get("action") != "review_lineage" or command.get("record") != event:
        raise ValueError("تغییر هویت IFC فقط از مسیر رسمی بازبینی ثبت می‌شود")
    if (event.get("status") != "reviewed_nonfinancial" or
            event.get("ready") is not False or
            event.get("commit_allowed") is not False or
            event.get("payable_rows") != [] or
            event.get("engineering_accepted") is not False):
        raise ValueError("بازبینی Split/Merge IFC مجوز متره یا پرداخت نیست")
    evidence_path = Path(event.get("evidence_path", ""))
    if (not evidence_path.is_file() or not evidence_path.stat().st_size or
            sha256(evidence_path.read_bytes()).hexdigest() != event.get("evidence_sha256")):
        raise ValueError("مدرک تغییر هویت IFC مفقود یا تغییرکرده است")
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("ساختار مدرک Split/Merge IFC نامعتبر است") from exc
    base = validate_lineage(
        previous, mode=event.get("mode"),
        previous_proposal_ids=event.get("previous_proposal_ids"),
        current_proposal_ids=event.get("current_proposal_ids"), evidence=evidence,
    )
    if any(event.get(k) != v for k, v in base.items()):
        raise ValueError("ثبت Split/Merge با مدرک مرجع IFC متفاوت است")


def review_lineage(service, project_id, *, mode, previous_proposal_ids,
                   current_proposal_ids, author, reviewer, evidence_path,
                   evidence_sha256, note, expected_digest):
    """Review a SHA-bound, nonfinancial split/merge in canonical SQLite/CAS."""
    from core.drawings.ifc_pipeline import _authorized
    from core.platform.concurrency import assert_unchanged
    from core.projects.project_model import _identity
    if not isinstance(expected_digest, str) or not expected_digest:
        raise ValueError("CAS برای Split/Merge IFC الزامی است")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("توضیح بازبینی تغییر هویت IFC الزامی است")
    _authorized(service, author, "edit")
    reviewer_user = _authorized(service, reviewer, "review")
    if _identity(author) == _identity(reviewer):
        raise ValueError("بازبین تغییر هویت IFC باید مستقل از نویسنده باشد")
    service.store._cache.pop(str(project_id), None)
    project = deepcopy(service.store.get(project_id))
    if project is None:
        raise KeyError(project_id)
    assert_unchanged({k: v for k, v in project.items() if k != "_meta"}, expected_digest)
    proof = Path(evidence_path)
    if (not proof.is_file() or not proof.stat().st_size or
            sha256(proof.read_bytes()).hexdigest() != evidence_sha256):
        raise ValueError("مدرک تغییر هویت IFC نامعتبر یا تغییرکرده است")
    try:
        evidence = json.loads(proof.read_text(encoding="utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("ساختار مدرک Split/Merge IFC نامعتبر است") from exc
    base = validate_lineage(
        project, mode=mode, previous_proposal_ids=previous_proposal_ids,
        current_proposal_ids=current_proposal_ids, evidence=evidence,
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        **base,
        "id": "IFC-LINEAGE-" + sha256(
            (str(project_id) + mode + evidence_sha256 + timestamp).encode()
        ).hexdigest(),
        "project_id": str(project_id),
        "status": "reviewed_nonfinancial",
        "created_at": timestamp,
        "author": author,
        "reviewer": reviewer,
        "reviewer_role": reviewer_user.role,
        "note": note.strip(),
        "evidence_path": str(proof.resolve()),
        "evidence_sha256": evidence_sha256,
    }
    project.setdefault("ifc_identity_lineages", []).append(record)
    service.store.save(
        project_id, project, expected_digest=expected_digest,
        ifc_command={"action": "review_lineage", "record": record},
    )
    return deepcopy(record)
