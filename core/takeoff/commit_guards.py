"""Shared fail-closed identity, quantity and BOQ invariants.

This module is deliberately independent of concrete/steel/MEP classifiers:
all reviewed workflows pass through identical guards before SQLite commit.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Iterable

from core.takeoff.boq import build_boq
from core.takeoff.units import normalize_unit

_REGISTRIES = ("beam_detail_register", "reviewed_structural_members", "reviewed_aec_systems")


def require_source_unused(project: dict, source_id: str, *, exclude: tuple[str, str] | None = None) -> None:
    """A measurement identity belongs to exactly one reviewed record across all domains.

    Multiple detail labels can refer to the same SHA-256 drawing; their measured
    region / source_id must still remain uniquely identified.
    """
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("شناسه یکتای برداشت الزامی است")
    source_id = source_id.strip()
    for registry in _REGISTRIES:
        entries = project.get(registry) or {}
        if not isinstance(entries, dict):
            raise ValueError("دفتر ثبت متره پروژه نامعتبر است")
        for key, record in entries.items():
            if exclude == (registry, key):
                continue
            if not isinstance(record, dict):
                raise ValueError("رکورد بازبینی متره نامعتبر است")
            if (record.get("data") or {}).get("source", {}).get("source_id") == source_id:
                raise ValueError("شناسه برداشت در عضو دیگری از پروژه تکرار شده است")
    for takeoff in project.get("takeoffs") or []:
        if not isinstance(takeoff, dict):
            raise ValueError("ساختار ردیف متره نامعتبر است")
        original = (takeoff.get("provenance") or {})
        if takeoff.get("source_id") == source_id or (
            isinstance(original, dict) and original.get("source_id") == source_id
        ):
            if exclude is None:
                raise ValueError("منبع برداشت پیش‌تر وارد ریزمتره شده است")
            # Committed records cannot be modified. This exception is for
            # idempotent checks of the current record in read-only contexts.
            raise ValueError("منبع برداشت قبلاً قطعی شده است")


def _intersection_ids(takeoff: dict) -> set[str]:
    params = takeoff.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("پارامترهای ثبت متره نامعتبر است")
    result: set[str] = set()
    listed=params.get("intersections", [])
    if not isinstance(listed, list):
        raise ValueError("فهرست کسورات بتن نامعتبر است")
    standalone=params.get("deduction")
    if standalone is not None:
        if not isinstance(standalone, dict) or not str(standalone.get("id") or "").strip():
            raise ValueError("شناسه منبع حفره/تقاطع سقف قابل ردیابی نیست")
        listed=list(listed)+[standalone]
    for deduction in listed:
        if not isinstance(deduction, dict):
            raise ValueError("مستند کسر هم‌پوشانی نامعتبر است")
        ident = deduction.get("id")
        if not isinstance(ident, str) or not ident.strip():
            raise ValueError("شناسه هم‌پوشانی کسرشده معتبر نیست")
        if ident in result:
            raise ValueError("یک هم‌پوشانی دوبار در عضو محاسبه شده است")
        result.add(ident)
    return result


def validate_commit_rows(
    project: dict, rows: Iterable[dict], *, source_id: str,
    expected_current_registry: tuple[str, str] | None = None,
) -> list[dict]:
    """Validate the full source identity and physical intersection graph.

    Returns copy of proposed rows only. Caller must atomically save both
    takeoffs and BOQ in the existing ProjectStore transaction.
    """
    existing = project.get("takeoffs") or []
    if not isinstance(existing, list):
        raise ValueError("ساختار ریزمتره پروژه معتبر نیست")
    require_source_unused(project, source_id, exclude=expected_current_registry)
    incoming = list(rows)
    if not incoming:
        raise ValueError("متره قابل ثبت نباید فاقد ریزقلم باشد")
    ids: set[str] = set()
    prior_ids: set[str] = set()
    already_deducted: set[str] = set()
    for row in existing:
        identity = row.get("source_id")
        if not isinstance(identity, str) or not identity:
            raise ValueError("شناسه منبع متره قبلی معتبر نیست")
        if identity in prior_ids:
            raise ValueError("ریزمتره ذخیره‌شده دارای شناسه تکراری است")
        prior_ids.add(identity)
        old = _intersection_ids(row)
        if old & already_deducted:
            raise ValueError("کسر هم‌پوشانی در ریزمتره قبلی تکرار شده است")
        already_deducted.update(old)
    fresh_deductions: set[str] = set()
    for row in incoming:
        if not isinstance(row, dict):
            raise ValueError("ساختار ردیف پیشنهادی نامعتبر است")
        sid = row.get("source_id")
        if not isinstance(sid, str) or not sid.strip() or sid in ids or sid in prior_ids:
            raise ValueError("ردیف با شناسه تکراری یا خالی قابل انتقال به BOQ نیست")
        ids.add(sid)
        quantities = row.get("quantities")
        if not isinstance(quantities, list) or not quantities:
            raise ValueError("ردیف متره بدون ریزکمیت قابل ثبت نیست")
        for q in quantities:
            if not isinstance(q, dict):
                raise ValueError("ساختار ریزکمیت متره نامعتبر است")
            if not str(q.get("code") or "").strip() or not str(q.get("title") or "").strip():
                raise ValueError("کد و شرح ریزکمیت الزامی است")
            normalize_unit(q.get("unit"))
            n = q.get("amount")
            if isinstance(n, bool):
                raise ValueError("مقدار بولی مجاز نیست")
            try:
                amount = float(n)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError("مقدار ریزمتره معتبر نیست") from exc
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError("مقدار ریزمتره باید مثبت و متناهی باشد")
        used = _intersection_ids(row)
        if used & (already_deducted | fresh_deductions):
            raise ValueError("کسر حجم مشترک بیش از یک بار ثبت شده است")
        fresh_deductions.update(used)
    return deepcopy(incoming)


def rebuild_project_boq(project: dict, new_takeoffs: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    """A single deterministic BOQ conversion for all three reviewed workflows."""
    takeoffs = deepcopy(list(new_takeoffs))
    inputs: list[dict] = []
    for takeoff in takeoffs:
        if not isinstance(takeoff, dict):
            raise ValueError("ردیف متره نامعتبر است")
        sid = takeoff.get("source_id")
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError("ریزمتره بدون منبع قابل ورود به BOQ نیست")
        for quantity in takeoff.get("quantities") or ():
            inputs.append({
                "source": sid, "source_id": sid, "source_type": "takeoff",
                "description": quantity["title"], "quantity": quantity["amount"],
                "unit": quantity["unit"], "item_code": quantity["code"],
                "price_code": quantity.get("price_code"),
                "unit_price": quantity.get("unit_price"),
                "category": takeoff.get("domain") or "building",
                "group": takeoff.get("system") or takeoff.get("domain") or "building",
                "factor": quantity.get("factor", 1),
                "waste_percent": quantity.get("waste_percent", 0),
                "allowance_quantity": quantity.get("allowance_quantity", 0),
                "status": quantity.get("status", "active"),
            })
    boq = build_boq(inputs)
    return takeoffs, boq



def require_reset_of_changed_approvals(previous: dict | None, updated: dict) -> None:
    """No engineering approval survives a substantive edit to its reviewed scope.

    The client must first save the changed scope as unreviewed/needs_review,
    then explicitly approve it in a subsequent revision. This prevents stale
    approver names from silently legitimizing new quantities or dimensions.
    """
    if not isinstance(previous, dict) or not isinstance(updated, dict):
        return
    for name in ("geometry", "formwork"):
        before, after = previous.get(name), updated.get(name)
        if not isinstance(before, dict) or not isinstance(after, dict):
            continue
        original = {k: v for k, v in before.items() if k not in ("approved_by", "status")}
        changed = {k: v for k, v in after.items() if k not in ("approved_by", "status")}
        if original == changed:
            continue
        was_approved = (before.get("status") in ("confirmed", "not_applicable")
                        or bool(before.get("approved_by")))
        still_approved = (after.get("status") in ("confirmed", "not_applicable")
                          or bool(after.get("approved_by")))
        if was_approved and still_approved:
            raise ValueError(
                f"اطلاعات تأییدشده {name} تغییر کرده؛ ابتدا تأیید پیشین را لغو و نسخه جدید را بازبینی کنید"
            )
    for group_field in ("bars", "rebars", "components"):
        former, current = previous.get(group_field), updated.get(group_field)
        if not isinstance(former, dict) or not isinstance(current, dict):
            continue
        for key, before in former.items():
            after = current.get(key)
            if not isinstance(before, dict) or not isinstance(after, dict):
                continue
            original = {k: v for k, v in before.items() if k not in ("approved_by", "status")}
            changed = {k: v for k, v in after.items() if k not in ("approved_by", "status")}
            if original == changed:
                continue
            if before.get("status") in ("confirmed", "not_applicable") and (
                after.get("status") in ("confirmed", "not_applicable")
            ):
                raise ValueError(
                    f"دیتایل تأییدشده {key} تغییر کرده؛ وضعیت گروه باید قبل از تأیید مجدد نیازمند بازبینی شود"
                )
