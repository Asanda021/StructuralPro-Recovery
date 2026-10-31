"""P7 E8: source-backed, non-payable IFC/DXF crosswalk integrity inspection.

Reuses the existing independent IFC review, stored SQLite crosswalk, source
sha256 and CAD item receipts. This is a READ ONLY audit, not a new crosswalk
registrar, model matcher, takeoff engine, or engineering/financial acceptance.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from core.drawings.ifc_pipeline import _binding, drawing_geometry_identity
from core.drawings.takeoff_session import DrawingTakeoffSession


def _unchanged_file(raw_path, expected_sha, label):
    if not isinstance(raw_path, str) or not raw_path.strip() or (
        not isinstance(expected_sha, str) or len(expected_sha) != 64
        or any(c not in "0123456789abcdef" for c in expected_sha)
    ):
        raise ValueError("مسیر یا SHA معتبر " + label + " موجود نیست")
    p = Path(raw_path)
    if not p.is_file() or sha256(p.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("مدرک یا منبع " + label + " تغییر کرده یا حذف شده است")
    return p


def inspect_reviewed_ifc_crosswalks(
    service, *, project_id: str, expected_project_version: int,
    selected_crosswalk_ids: tuple[str, ...],
) -> dict:
    if (not isinstance(project_id, str) or not project_id.strip() or
        type(expected_project_version) is not int or
        not isinstance(selected_crosswalk_ids, tuple) or
        not selected_crosswalk_ids or len(selected_crosswalk_ids) > 1000 or
        len(selected_crosswalk_ids) != len(set(selected_crosswalk_ids)) or
        any(not isinstance(x, str) or not x or x != x.strip()
            for x in selected_crosswalk_ids)):
        raise ValueError("شناسه‌ها و نسخه صریح Crosswalk لازم‌اند")
    before_digest = service.store.current_digest(project_id)
    project = service.open_project(project_id)
    if (not isinstance(project, dict) or project.get("id") != project_id or
        project.get("_meta", {}).get("version") != expected_project_version):
        raise ValueError("نسخه اصلی پروژه با درخواست تطبیق ندارد")
    links = project.get("ifc_2d_crosswalks", [])
    sessions = project.get("drawing_sessions", {})
    if not isinstance(links, list) or not isinstance(sessions, dict):
        raise ValueError("دفتر واقعی Crosswalk و نشست‌ها معتبر نیست")
    by_id = {}
    for link in links:
        if (not isinstance(link, dict) or not isinstance(link.get("id"), str)
            or not link["id"] or link["id"] in by_id):
            raise ValueError("دفتر Crosswalk دارای شناسه نامعتبر یا تکراری است")
        by_id[link["id"]] = link
    if any(sid not in by_id for sid in selected_crosswalk_ids):
        raise ValueError("پیوند خواسته‌شده در پروژه ذخیره نشده است")
    out = []
    selected = set(selected_crosswalk_ids)
    for sid in selected_crosswalk_ids:
        record = by_id[sid]
        if (record.get("status") != "approved" or
            record.get("commit_allowed") is not False or
            record.get("payable_rows") != [] or
            any(other.get("supersedes") == sid for other in links)):
            raise ValueError("Crosswalk تاریخی/منسوخ یا غیرمجاز برای تأیید نیست")
        # The canonical IFC binding reopens source bytes, verifies reviewed
        # proposal and identity, rejects lineage/supersession, and checks
        # the real member + storey. No GlobalId string guessing.
        decision, _element = _binding(project, record.get("proposal_id"))
        if (record.get("global_id") != decision.get("global_id") or
            record.get("member_id") != decision.get("member_id") or
            record.get("floor_id") != decision.get("floor_id") or
            record.get("ifc_document") != decision.get("document")):
            raise ValueError("مالکیت و منشأ IFC با مدارک مستقل تطبیق ندارند")
        author, reviewer = record.get("author"), record.get("reviewer")
        if (not isinstance(author, str) or not isinstance(reviewer, str) or
            not author or not reviewer or author == reviewer):
            raise ValueError("نویسنده و بازبین مستقل Crosswalk نامعتبرند")
        collab = service.collaboration
        user = collab.users.get(reviewer)
        if user is None or not collab.roles[user.role].allows("review"):
            raise PermissionError("بازبین مستقل Crosswalk مجوز جاری ندارد")
        evidence_path = _unchanged_file(
            record.get("evidence_path"), record.get("evidence_sha256"),
            "Crosswalk",
        )
        try:
            verified_proof = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("مدرک Crosswalk JSON معتبر نیست") from exc
        if verified_proof != record.get("coordinate_evidence"):
            raise ValueError("مدرک مختصات Crosswalk با رسید ذخیره‌شده فرق دارد")
        saved = sessions.get(record.get("session_id"))
        drawing = record.get("drawing")
        if (not isinstance(saved, dict) or not isinstance(drawing, dict) or
            saved.get("id") != record.get("session_id") or
            type(saved.get("revision")) is not int or
            drawing.get("session_revision") != saved.get("revision") or
            saved.get("source_sha256") != drawing.get("source_sha256") or
            not isinstance(saved.get("session"), dict)):
            raise ValueError("نشست/Revision اصلی منبع دوبعدی مطابقت ندارد")
        ds = DrawingTakeoffSession.from_dict(saved["session"])
        _unchanged_file(
            ds.drawing_source, drawing.get("source_sha256"), "CAD/PDF")
        if ds.source_sha256 != drawing["source_sha256"]:
            raise ValueError("هش نشست با فایل CAD/PDF ناسازگار است")
        try:
            item = ds.find(record.get("item_id"))
        except (KeyError, ValueError) as exc:
            raise ValueError("جزء دوبعدی منبع Crosswalk یافت نشد") from exc
        item_digest = sha256(json.dumps(
            item.to_dict(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if (drawing.get("item_digest") != item_digest or
            item.page != drawing.get("page") or
            drawing.get("geometry_identity") != drawing_geometry_identity(
                ds.source_sha256, item.page, item.kind, item.geometry, item.holes)):
            raise ValueError("هندسه، صفحه یا رسید جزء CAD/PDF دستکاری شده است")
        # This is documentary navigation only. Neither crosswalk nor IFC
        # member ownership permits a second paid quantity.
        out.append({
            "crosswalk_id": sid,
            "ifc_global_id": decision["global_id"],
            "member_id": decision["member_id"],
            "floor_id": decision["floor_id"],
            "proposal_id": decision["proposal_id"],
            "ifc_source_sha256": decision["document"]["source_sha256"],
            "drawing_source_sha256": drawing["source_sha256"],
            "drawing_session_id": record["session_id"],
            "drawing_item_id": record["item_id"],
            "source_item_digest": item_digest,
            "reviewer_id": reviewer,
            "status": "VERIFIED_NONFINANCIAL_CROSSWALK",
        })
    # Re-examine IFC evidence after consuming all sources, and assert CAS
    # before delivering a stale cross-view audit.
    for sid in selected_crosswalk_ids:
        record = by_id[sid]
        _binding(project, record["proposal_id"])
        _unchanged_file(record["evidence_path"], record["evidence_sha256"], "Crosswalk")
        _unchanged_file(record["drawing"]["path"], record["drawing"]["source_sha256"], "CAD/PDF")
    if (service.store.current_digest(project_id) != before_digest or
        service.open_project(project_id) != project):
        raise RuntimeError("پروژه در حین اعتبارسنجی Crosswalk تغییر کرد")
    owners = {}
    for row in out:
        owners.setdefault((row["floor_id"], row["member_id"]), []).append(row)
    multi = []
    for (floor, member), rows in owners.items():
        if len({r["drawing_session_id"] + ":" + r["drawing_item_id"] for r in rows}) > 1:
            multi.append({
                "floor_id": floor, "member_id": member,
                "crosswalk_ids": sorted(r["crosswalk_id"] for r in rows),
                "status": "INDEPENDENT_ENGINEER_REVIEW_REQUIRED",
                "financial_impact": None,
            })
    return {
        "project_id": project_id, "project_version": expected_project_version,
        "source_project_digest": before_digest,
        "status": ("REVIEW_REQUIRED" if multi else "VERIFIED_SOURCE_REFERENCES_ONLY"),
        "crosswalks": out,
        "multiple_physical_claims": multi,
        "quantity_inferred": False,
        "commit_allowed": False,
        "payable_rows": [],
        "engineering_accepted": False,
        "readonly": True,
    }
