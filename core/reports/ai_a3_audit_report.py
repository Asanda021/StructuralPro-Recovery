"""P7 priority 6 / A3: evidence-backed, read-only persisted AI takeoff audit.

Reports ONLY AI-assisted measurements actually stored in ProjectStore and BOQ.
Unpersisted rejected proposals, model identity and reviewer identity are
explicitly NOT_RECORDED. No model inference, retroactive approval or new
quantity calculation is performed.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from core.drawings.takeoff_bridge import session_to_boq_rows, verified_measurement_identities
from core.reports.decimal_values import decimal_value
from core.reports.custom_batch import _source_rows
from core.reports.bundle import build_bundle_manifest
from core.reports.technical_office_dossier import _read_back
from core.reports import exporters

COLUMNS = (
    ("row_no", "ردیف"), ("source_id", "شناسه ثبت AI"),
    ("drawing_session_id", "نشست نقشه"), ("session_item_id", "جزء برداشت"),
    ("drawing_sha256", "هش منبع نقشه"), ("measurement_identity", "هویت اندازه‌گیری"),
    ("source_quantity", "مقدار از نقشه"), ("committed_quantity", "مقدار ثبت‌شده"),
    ("unit", "واحد"), ("source_match", "انطباق منبع"),
    ("human_confirmation", "سند تأیید انسانی"),
    ("independent_reviewer", "هویت بازبین مستقل"),
    ("model_provenance", "منشأ مدل AI"), ("financial_authority", "اختیار مالی"),
)
FORMATS = ("pdf", "xlsx", "docx", "csv")


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value):
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _context(service, *, project_id, expected_project_version):
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("شناسه پروژه معتبر لازم است")
    if type(expected_project_version) is not int:
        raise ValueError("نسخه پروژه باید عدد صحیح صریح باشد")
    digest = service.store.current_digest(project_id)
    project = service.open_project(project_id)
    if (not isinstance(project, dict) or project.get("id") != project_id or
        project.get("_meta", {}).get("version") != expected_project_version):
        raise ValueError("نسخه پروژه تغییر کرده است")
    return project, digest


def _rows(project):
    # Reuse canonical financial/source integrity checks; this does not
    # import AI prose as authority and never prices a quantity.
    _source_rows(project, "takeoff")
    source_receipts = {}
    for item in project.get("takeoffs", []):
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str):
            raise ValueError("ریزمتره ذخیره‌شده نامعتبر است")
        sid = item["source_id"]
        if sid in source_receipts:
            raise ValueError("شناسه منبع تکراری است")
        source_receipts[sid] = item
    boq_references = Counter(
        source for row in project.get("boq", [])
        for source in (row.get("source_ids") or [])
    )
    entries = []
    used_measurements = set()
    for item in project.get("takeoffs", []):
        if item.get("domain") != "drawing_ai":
            continue
        source_id = item["source_id"]
        if (item.get("ai_generated") is not True or
            not isinstance(item.get("params"), dict) or
            not isinstance(item.get("provenance"), dict) or
            not isinstance(item.get("quantities"), list) or
            len(item["quantities"]) != 1 or
            boq_references[source_id] != 1):
            raise ValueError("رسید قطعی AI/BOQ و منشأ آن ناقص است")
        params, receipt = item["params"], item["provenance"]
        session_id = item.get("drawing_session_id")
        measurement_id = params.get("session_item_id")
        revision = params.get("drawing_revision")
        saved = (project.get("drawing_sessions") or {}).get(session_id)
        if (not isinstance(session_id, str) or not session_id or
            not isinstance(measurement_id, str) or not measurement_id or
            type(revision) is not int or revision < 1 or
            not isinstance(saved, dict) or saved.get("id") != session_id or
            measurement_id not in (saved.get("ai_committed_item_ids") or []) or
            source_id.split(":")[:3] != ["ai-takeoff", session_id, str(revision)] or
            params.get("drawing_session_id") != session_id or
            params.get("source_sha256") != saved.get("source_sha256") or
            params.get("drawing_source") != saved.get("drawing_source") or
            receipt.get("drawing_session_id") != session_id or
            receipt.get("source_id") != source_id):
            raise ValueError("رسید AI و نسخه اصلی نشست نقشه همخوان نیستند")
        k = (session_id, measurement_id)
        if k in used_measurements:
            raise ValueError("یک اندازه‌گیری AI بیش از یک بار به BOQ منتقل شده است")
        used_measurements.add(k)
        canonical = session_to_boq_rows(
            saved["session"], session_id=session_id,
            selected_item_ids=(measurement_id,))
        verified_measurement_identities(saved, canonical)
        if len(canonical) != 1:
            raise ValueError("هویت اندازه‌گیری AI یکتا نیست")
        original = canonical[0]
        stored = item["quantities"][0]
        if (params.get("measurement_identity") != original["measurement_identity"] or
            stored.get("unit") != original["unit"] or
            stored.get("source_ref") != original["source"] or
            receipt.get("source_ref") != original["source"] or
            stored.get("page") != original["page"] or
            params.get("calibration") != original["calibration"]):
            raise ValueError("هویت، واحد، صفحه یا مقیاس ثبت AI با نقشه اصلی تطبیق ندارد")
        evidence = params.get("evidence")
        if (not isinstance(evidence, dict) or
            evidence.get("source_ref") != original["source"]):
            raise ValueError("ارجاع شواهد AI به نقشه اصلی قابل اثبات نیست")
        if original["kind"] in ("length", "area"):
            calibration = original["calibration"] or {}
            if (not isinstance(calibration, dict) or
                decimal_value(evidence.get("meters_per_pixel"), field="AI scale") !=
                decimal_value(calibration.get("meters_per_pixel"), field="source scale")):
                raise ValueError("مقیاس گزارش AI با مقیاس منبع مطابقت ندارد")
        confidence = decimal_value(params.get("confidence"), field="AI confidence")
        if confidence < 0 or confidence > 1:
            raise ValueError("درجه اطمینان AI خارج از دامنه معتبر است")
        original_q = decimal_value(original["quantity"], field="original measured quantity")
        committed_q = decimal_value(stored.get("amount"), field="committed AI quantity")
        delta = abs(original_q - committed_q)
        tolerance = max(Decimal("0.000000001"), abs(original_q) * Decimal("0.000000001"))
        if delta > tolerance:
            raise ValueError("مقدار ثبت‌شده AI با اندازه‌گیری اصلی تفاوت دارد")
        # A tiny difference which passed the legacy commit-time numeric
        # tolerance is disclosed, never represented as bit-for-bit exact.
        comparison = ("EXACT_SOURCE_QUANTITY" if delta == 0
                      else "COMMIT_TOLERANCE_REVIEW_REQUIRED")
        entries.append({
            "row_no": len(entries) + 1,
            "source_id": source_id,
            "drawing_session_id": session_id,
            "session_item_id": measurement_id,
            "drawing_sha256": original["source_sha256"],
            "measurement_identity": original["measurement_identity"],
            "source_quantity": str(original_q),
            "committed_quantity": str(committed_q),
            "unit": original["unit"],
            "source_match": comparison,
            "human_confirmation": "AT_COMMIT_BOOLEAN_ONLY",
            "independent_reviewer": "NOT_RECORDED_IN_LEGACY_RECEIPT",
            "model_provenance": "NOT_RECORDED_IN_LEGACY_RECEIPT",
            "financial_authority": "NONE",
        })
    if not entries:
        raise ValueError("هیچ برداشت AI ثبت‌شده و قابل ممیزی در پروژه وجود ندارد")
    return entries


def preview_ai_a3_audit(service, *, project_id: str, expected_project_version: int):
    project, digest = _context(
        service, project_id=project_id,
        expected_project_version=expected_project_version)
    records = _rows(project)
    if service.store.current_digest(project_id) != digest or service.open_project(project_id) != project:
        raise RuntimeError("منبع پروژه در حین ممیزی AI تغییر کرده است")
    return {
        "schema": "structuralpro.phase7.ai-a3-audit.v1",
        "project_id": project_id,
        "project_version": expected_project_version,
        "source_project_digest": digest,
        "records": records,
        "record_count": len(records),
        "evidence_status": "PERSISTED_AI_SOURCE_VERIFIED",
        "human_confirmation_scope": "BOOLEAN_AT_COMMIT_ONLY",
        "independent_reviewer_identity": "NOT_RECORDED",
        "model_identity_and_runtime_sha": "NOT_RECORDED",
        "rejected_or_uncommitted_proposals": "NOT_PERSISTED_NOT_AUDITED",
        "financial_and_engineering_approval": False,
        "source_is_model_generated_truth": False,
        "mutation": False,
    }


def export_ai_a3_audit_package(
    service, *, project_id: str, expected_project_version: int,
    destination: str | Path,
):
    """Atomic four-format Persian report from genuine saved AI BOQ receipts."""
    target = Path(destination)
    if target.exists() or any(p.is_symlink() for p in (target, *target.parents)):
        raise FileExistsError("مسیر مقصد موجود یا لینک نمادین است")
    report = preview_ai_a3_audit(
        service, project_id=project_id,
        expected_project_version=expected_project_version)
    # Re-read after preview, because source-byte and CAS checks are authority.
    digest = report["source_project_digest"]
    baseline = service.open_project(project_id)
    if service.store.current_digest(project_id) != digest:
        raise RuntimeError("پروژه پیش از خروجی AI تغییر کرده است")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix="structuralpro_p7_p6_a3_") as work:
        stage = Path(work) / "package"
        stage.mkdir()
        items = []
        metadata = {
            "شناسه پروژه": project_id,
            "نسخه پروژه": str(expected_project_version),
            "هش پروژه": digest,
            "وضعیت بازبین مستقل": "ثبت نشده در رسیدهای قدیمی",
            "وضعیت مدل AI": "شناسه و هش مدل ثبت نشده",
            "دامنه": "فقط برداشت AI ثبت‌شده؛ نه همه پیشنهادهای ردشده",
            "تأیید مهندسی و مالی": "خیر",
            "_page_format": "A3",
            "_orientation": "landscape",
        }
        for fmt in FORMATS:
            path = stage / ("ai-a3-audit." + fmt)
            getattr(exporters, "export_" + fmt)(
                report["records"], path, title="گزارش ممیزی AI/A3 استراکچرال پرو",
                metadata=metadata, columns=COLUMNS)
            _read_back(path, fmt, "ai_a3")
            items.append(path)
        manifest = {
            **build_bundle_manifest(items, project_id=project_id,
                                    revision=str(expected_project_version)),
            "schema": report["schema"],
            "source_project_digest": digest,
            "project_version": expected_project_version,
            "record_count": report["record_count"],
            "rows_sha256": _sha(report["records"]),
            "independent_reviewer_identity": report["independent_reviewer_identity"],
            "model_identity_and_runtime_sha": report["model_identity_and_runtime_sha"],
            "rejected_or_uncommitted_proposals": report["rejected_or_uncommitted_proposals"],
            "human_confirmation_scope": report["human_confirmation_scope"],
            "financial_and_engineering_approval": False,
            "source_is_model_generated_truth": False,
            "physical_windows_office_print": "NOT_TESTED_PHASE8",
            "mutation": False,
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8")
        after = preview_ai_a3_audit(
            service, project_id=project_id,
            expected_project_version=expected_project_version)
        if (after["source_project_digest"] != digest or
            _sha(after["records"]) != manifest["rows_sha256"] or
            service.store.current_digest(project_id) != digest or
            service.open_project(project_id) != baseline):
            raise RuntimeError("داده و شواهد AI پیش از انتشار تغییر کرده‌اند")
        if target.exists():
            raise FileExistsError("مسیر مقصد در حین تهیه گزارش ساخته شده است")
        os.rename(stage, target)
    return {"destination": str(target), "manifest": manifest}
