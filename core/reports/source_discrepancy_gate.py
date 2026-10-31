"""Phase 7 priority 5 E8: fail-closed, source-backed cross-session discrepancy preflight.

Read-only preflight for a *persisted, uncommitted* PDF/CAD takeoff selection.
The existing geometry, PDF vector, CAD identity and BOQ/audit engines are the
authorities; this module never infers new dimensions or decides that a geometry
difference is an approved design revision.
"""
from __future__ import annotations

from decimal import Decimal

from core.drawings.takeoff_bridge import (
    session_to_boq_rows, verified_measurement_identities,
)
from core.reports.custom_batch import _source_rows
from core.reports.decimal_values import decimal_value


def inspect_pending_source_discrepancies(
    service, *, project_id: str, expected_project_version: int,
    session_id: str, selected_item_ids: tuple[str, ...],
) -> dict:
    """Inspect pending drawing evidence against existing committed BOQ sources.

    Matching *documented member + floor + code + unit* between independent
    takeoffs is only a potential conflict; it is NEVER proof of duplicated
    geometry. No auto-merge or difference acceptance is permitted.
    """
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("شناسه پروژه الزامی است")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("شناسه نشست نقشه الزامی است")
    if (type(expected_project_version) is not int or
        not isinstance(selected_item_ids, tuple) or not selected_item_ids or
        len(selected_item_ids) > 1000 or
        len(selected_item_ids) != len(set(selected_item_ids)) or
        not all(isinstance(x, str) and x and x == x.strip()
                for x in selected_item_ids)):
        raise ValueError("انتخاب صریح و یکتای متره/نسخه معتبر لازم است")

    digest = service.store.current_digest(project_id)
    project = service.open_project(project_id)
    if (not isinstance(project, dict) or project.get("id") != project_id or
        project.get("_meta", {}).get("version") != expected_project_version):
        raise ValueError("نسخه فعلی پروژه تغییر کرده است")
    sessions = project.get("drawing_sessions")
    record = sessions.get(session_id) if isinstance(sessions, dict) else None
    if (not isinstance(record, dict) or record.get("id") != session_id or
        type(record.get("revision")) is not int or
        not isinstance(record.get("session"), dict) or
        record.get("source_sha256") != record["session"].get("source_sha256") or
        record.get("drawing_source") != record["session"].get("drawing_source")):
        raise ValueError("رسید منبع/نشست ثبت‌شده معتبر نیست")
    committed = record.get("committed_item_ids")
    if not isinstance(committed, list):
        raise ValueError("فهرست انتقال‌های BOQ معتبر نیست")
    if set(selected_item_ids) & set(committed):
        raise ValueError("برداشت مورد بررسی قبلاً به BOQ منتقل شده است")

    pending = session_to_boq_rows(
        record["session"], session_id=session_id,
        selected_item_ids=selected_item_ids,
    )
    verified_measurement_identities(record, pending)
    # This is the preexisting, fully guarded canonical BOQ+takeoff/source
    # pipeline, including original file SHA and effective amendments.
    approved_rows = _source_rows(project, "takeoff")
    records_by_source = {
        row.get("source_id"): row for row in project.get("takeoffs", [])
        if isinstance(row, dict)
    }
    if len(records_by_source) != len(project.get("takeoffs", [])):
        raise ValueError("منبع ثبت‌شده BOQ تکراری است")
    actual_approved = []
    for row in approved_rows:
        rec = records_by_source.get(row["source_id"])
        if rec is None:
            raise ValueError("رسید ریزمتره واقعی یافت نشد")
        if rec.get("domain") != "drawing":
            continue  # Out of scope, not treated as independent verified CAD.
        evidence = (rec.get("params") or {}).get("geometry_evidence")
        if not isinstance(evidence, dict):
            raise ValueError("هویت هندسی برداشت قبلی ناقص است")
        for field in ("floor_id", "member_id"):
            if not isinstance(evidence.get(field), str) or not evidence[field].strip():
                raise ValueError("عضو یا طبقه در برداشت قبلی مستند نیست")
        actual_approved.append({
            "source_id": row["source_id"],
            "floor_id": evidence["floor_id"],
            "member_id": evidence["member_id"],
            "item_code": row["item_code"],
            "unit": row["unit"],
            "quantity": decimal_value(row["quantity"], field="committed quantity", non_negative=True),
            "source_sha256": (rec.get("params") or {}).get("source_sha256"),
            "drawing_session_id": rec.get("drawing_session_id"),
            "measurement_identity": (rec.get("params") or {}).get("measurement_identity"),
        })
        if not actual_approved[-1]["source_sha256"] or not actual_approved[-1]["measurement_identity"]:
            raise ValueError("رسید هش یا شناسه اندازه‌گیری قبلی ناقص است")

    conflicts, inspected = [], []
    for row in pending:
        proof = row.get("geometry_evidence")
        if row.get("kind") != "area" or not isinstance(proof, dict):
            raise ValueError("در این قرارداد فقط سطح با هویت هندسی مستند پشتیبانی می‌شود")
        floor = proof.get("floor_id")
        member = proof.get("member_id")
        if not all(isinstance(v, str) and v.strip() and v == v.strip()
                   for v in (floor, member)):
            raise ValueError("عضو/طبقه صریح برای تطبیق فیزیکی لازم است")
        quantity = decimal_value(row["quantity"], field="pending quantity", non_negative=True)
        candidate = {
            "takeoff_id": row["takeoff_id"],
            "source_id": row["source_id"],
            "source_sha256": record["source_sha256"],
            "source_revision": record["revision"],
            "floor_id": floor,
            "member_id": member,
            "item_code": row["item_code"],
            "unit": row["unit"],
            "quantity": str(quantity),
            "measurement_identity": row.get("measurement_identity"),
        }
        inspected.append(candidate)
        for stored in actual_approved:
            if (stored["floor_id"], stored["member_id"], stored["item_code"], stored["unit"]) != (
                floor, member, row["item_code"], row["unit"]
            ):
                continue
            code = ("POTENTIAL_DUPLICATE_MEMBER_SOURCE"
                    if stored["quantity"] == quantity
                    else "MEMBER_SOURCE_QUANTITY_DISCREPANCY")
            conflicts.append({
                "code": code,
                "status": "HUMAN_REVIEW_REQUIRED",
                "candidate": candidate,
                "committed": {
                    **stored,
                    "quantity": str(stored["quantity"]),
                },
                "reason": "یک عضو/طبقه/کد/واحد با دو رسید مستقل؛ تشخیص هم‌پوشانی نیازمند بررسی مهندس است",
            })

    if service.store.current_digest(project_id) != digest or service.open_project(project_id) != project:
        raise RuntimeError("پروژه هنگام بررسی مغایرت تغییر کرده است")
    return {
        "project_id": project_id,
        "project_version": expected_project_version,
        "session_id": session_id,
        "session_revision": record["revision"],
        "source_sha256": record["source_sha256"],
        "scope": "source_verified_uncommitted_drawing_areas_vs_existing_drawing_boq",
        "status": "REVIEW_REQUIRED" if conflicts else "NO_CROSS_SESSION_MEMBER_CONFLICT_FOUND",
        "allowed_to_commit": not conflicts,
        "approved_for_engineering_release": False,
        "mutation": False,
        "candidates": inspected,
        "conflicts": sorted(conflicts, key=lambda x: (
            x["candidate"]["source_id"], x["committed"]["source_id"]
        )),
    }


def require_no_pending_source_discrepancies(service, **kwargs):
    """Fail closed for automatic takeoff-to-BOQ flow, never self-approve clashes."""
    result = inspect_pending_source_discrepancies(service, **kwargs)
    if result["conflicts"]:
        raise ValueError("مغایرت احتمالی منابع متره وجود دارد؛ تأیید مستقل مهندس الزامی است")
    return result
