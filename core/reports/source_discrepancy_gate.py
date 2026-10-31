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
        type(expected_project_version) is not int or
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
    ai_committed = record.get("ai_committed_item_ids", [])
    if not isinstance(ai_committed, list):
        raise ValueError("فهرست انتقال‌های هوشمند BOQ معتبر نیست")
    if set(selected_item_ids) & (set(committed) | set(ai_committed)):
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
        domain = rec.get("domain")
        if domain not in ("drawing", "drawing_ai"):
            continue
        params = rec.get("params")
        if not isinstance(params, dict):
            raise ValueError("رسید برداشت قبلی معتبر نیست")
        original_code, original_unit = row["item_code"], row["unit"]
        if domain == "drawing_ai":
            # AI rows predate persisted geometry_evidence. Recover exact
            # member ownership from the original SHA-verified drawing session.
            if rec.get("item") != "area":
                continue
            source_sid = rec.get("drawing_session_id")
            source_item = params.get("session_item_id")
            prior = sessions.get(source_sid) if isinstance(sessions, dict) else None
            if (not isinstance(source_sid, str) or not source_sid or
                not isinstance(source_item, str) or not source_item or
                not isinstance(prior, dict) or prior.get("id") != source_sid or
                params.get("source_sha256") != prior.get("source_sha256") or
                params.get("drawing_source") != prior.get("drawing_source") or
                source_item not in (prior.get("ai_committed_item_ids") or [])):
                raise ValueError("سند منشأ یا نشست AI قبلی معتبر نیست")
            verified_rows = session_to_boq_rows(
                prior["session"], session_id=source_sid,
                selected_item_ids=(source_item,))
            verified_measurement_identities(prior, verified_rows)
            if len(verified_rows) != 1 or verified_rows[0]["kind"] != "area":
                raise ValueError("نوع هندسه AI قبلی قابل اثبات نیست")
            original = verified_rows[0]
            saved_quantities = rec.get("quantities")
            if (not isinstance(saved_quantities, list) or len(saved_quantities) != 1 or
                not isinstance(saved_quantities[0], dict) or
                params.get("measurement_identity") != original["measurement_identity"] or
                saved_quantities[0].get("unit") != original["unit"] or
                decimal_value(saved_quantities[0].get("amount"), field="AI source", non_negative=True) !=
                decimal_value(original["quantity"], field="original source", non_negative=True) or
                decimal_value(row["quantity"], field="BOQ source", non_negative=True) !=
                decimal_value(original["quantity"], field="original source", non_negative=True)):
                raise ValueError("کمیت، هویت یا واحد AI با نقشه اصلی مطابقت ندارد")
            evidence = original.get("geometry_evidence")
            original_code, original_unit = original["item_code"], original["unit"]
        else:
            evidence = params.get("geometry_evidence")
            if not isinstance(evidence, dict) and isinstance(params.get("cad_evidence"), dict):
                # Reviewed CAD line/area takeoffs have *cad_evidence*, not
                # PDF polygon geometry_evidence. Re-validate their actual
                # source bytes, entity, review, session and committed amount
                # before using the documented floor/member as an E8 owner.
                # Never skip an unverifiable historical CAD claim.
                prior_sid = rec.get("drawing_session_id")
                prior_item_id = rec.get("drawing_takeoff_id")
                prior = sessions.get(prior_sid) if isinstance(sessions, dict) else None
                if (not isinstance(prior_sid, str) or not prior_sid or
                    not isinstance(prior_item_id, str) or not prior_item_id or
                    not isinstance(prior, dict) or prior.get("id") != prior_sid or
                    prior_item_id not in (prior.get("committed_item_ids") or []) or
                    params.get("source_sha256") != prior.get("source_sha256") or
                    params.get("drawing_source") != prior.get("drawing_source")):
                    raise ValueError("رسید اتصال CAD قبلی به نشست اصلی معتبر نیست")
                prior_rows = session_to_boq_rows(
                    prior["session"], session_id=prior_sid,
                    selected_item_ids=(prior_item_id,),
                )
                verified_measurement_identities(prior, prior_rows)
                if len(prior_rows) != 1 or not isinstance(prior_rows[0].get("cad_evidence"), dict):
                    raise ValueError("رسید برداشت CAD قبلی قابل احراز نیست")
                original = prior_rows[0]
                original_quantity = (rec.get("quantities") or [])
                if (rec.get("domain") != "drawing" or
                    rec.get("item") != original["kind"] or
                    rec.get("source_id") != original["source_id"] or
                    params.get("measurement_identity") != original["measurement_identity"] or
                    params.get("cad_evidence") != original["cad_evidence"] or
                    len(original_quantity) != 1 or
                    not isinstance(original_quantity[0], dict) or
                    original_quantity[0].get("code") != original["item_code"] or
                    original_quantity[0].get("unit") != original["unit"] or
                    row["item_code"] != original["item_code"] or
                    row["unit"] != original["unit"] or
                    decimal_value(original_quantity[0].get("amount"), field="CAD stored amount", non_negative=True) !=
                    decimal_value(original["quantity"], field="CAD source amount", non_negative=True) or
                    decimal_value(row["quantity"], field="CAD BOQ amount", non_negative=True) !=
                    decimal_value(original["quantity"], field="CAD source amount", non_negative=True)):
                    raise ValueError("هویت یا کمیت CAD قبلی با منبع اصلی مطابقت ندارد")
                evidence = original["cad_evidence"]
                original_code, original_unit = original["item_code"], original["unit"]
        if not isinstance(evidence, dict):
            raise ValueError("هویت هندسی برداشت قبلی ناقص است")
        for field in ("floor_id", "member_id"):
            if not isinstance(evidence.get(field), str) or not evidence[field].strip():
                raise ValueError("عضو یا طبقه در برداشت قبلی مستند نیست")
        actual_approved.append({
            "source_id": row["source_id"],
            "floor_id": evidence["floor_id"],
            "member_id": evidence["member_id"],
            "item_code": original_code,
            "unit": original_unit,
            "source_mode": domain,
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

    # Final source-byte validation: a document replaced during review must
    # never be treated as the unchanged source from the initial read.
    verified_measurement_identities(record, pending)
    _source_rows(project, "takeoff")
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
        "source_preflight_clear": not conflicts,
        "final_commit_authority": False,
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
