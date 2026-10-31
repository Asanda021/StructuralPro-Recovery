"""Phase 7 priority 4: audited quantity changes between *real SQLite revisions*.

The authoritative previous/current snapshots are fetched through the existing
ProjectStore.revisions API; caller-supplied dictionaries can NEVER impersonate
a historical revision. Original BOQ / takeoff auditing and drawing source
validation are reused. No new measurement, price or schedule calculation.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, localcontext, Inexact, Rounded, DecimalException
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from core.reports.bundle import build_bundle_manifest
from core.reports.custom_batch import _source_rows
from core.reports.decimal_values import decimal_value, exact_sum
from core.reports.project_report import build_report


def _historical(service, pid, before_version, after_version):
    if (type(before_version) is not int or type(after_version) is not int or
            before_version < 1 or before_version >= after_version):
        raise ValueError("دو نسخه واقعی و افزایشی از تاریخچه پروژه لازم است")
    versions = service.store.revisions(pid)
    if not isinstance(versions, list):
        raise ValueError("تاریخچه معتبر پروژه در دسترس نیست")
    found = {}
    for item in versions:
        if (type(item.get("version")) is not int or
            not isinstance(item.get("payload"), dict)):
            raise ValueError("رکورد تاریخچه نامعتبر است")
        if item["version"] in (before_version, after_version):
            if item["version"] in found:
                raise ValueError("نسخه تکراری در تاریخچه پروژه")
            payload = deepcopy(item["payload"])
            if payload.get("id") != pid or "_meta" in payload:
                raise ValueError("شناسه یا متاداده نسخه تاریخی ناسازگار است")
            payload["_meta"] = {"version": item["version"], "id": pid}
            found[item["version"]] = payload
    if set(found) != {before_version, after_version}:
        raise ValueError("نسخه گزارش در تاریخچه واقعی پروژه وجود ندارد")
    return found[before_version], found[after_version]


def _indexed(snapshot):
    # Reuses existing audit_boq, effective_takeoffs, source receipts, actual
    # source file SHA and fail-closed unit/quantity validation.
    rows = _source_rows(snapshot, "takeoff")
    index = {}
    for row in rows:
        sid = row.get("source_id")
        code = row.get("item_code")
        unit = row.get("unit")
        if (not isinstance(sid, str) or not sid.strip() or
            not isinstance(code, str) or not code.strip() or
            not isinstance(unit, str) or not unit.strip()):
            raise ValueError("ردیف ریزمتره با شناسه و واحد معتبر لازم است")
        key = (sid, code, unit)
        if key in index:
            raise ValueError("منبع ریزمتره، کد و واحد تکراری است")
        amount = decimal_value(row.get("quantity"), field="takeoff quantity", non_negative=True)
        index[key] = {
            "quantity": amount, "description": row.get("description", ""),
            "floor": row.get("floor") or "",
            "member": row.get("member") or "",
            "revision": str(row.get("revision", "")),
        }
    return index



def _verified_financial_effect(before: dict, after: dict, indexed_keys):
    """Quantity-only price effect; None means independently unprovable.

    Only a common approved, exact-encoded and physically verified pricebook,
    explicit shared currency, unmixed one-source BOQ rows and invariant
    rates/factors permit a money result. Actual estimate & pricebook engines
    validate every historical quantity and unit; this function only compares.
    """
    books = [p.get("user_pricebook_review") for p in (before, after)]
    if not all(isinstance(book, dict) and book.get("status") == "approved" for book in books):
        return None
    if any(book.get("numeric_encoding_version") != 2 for book in books):
        return None
    b0, b1 = books
    currency = b0.get("currency")
    if (currency not in ("IRR", "IRT") or b1.get("currency") != currency or
        not b0.get("sha256") or b0.get("sha256") != b1.get("sha256") or
        b0.get("source_version") != b1.get("source_version") or
        b0.get("receipt", {}).get("year") != b1.get("receipt", {}).get("year")):
        return None

    from core.reports.aec_office_package import audit_boq
    from core.commercial.exact_values import number, exact
    # Reuse original source verification; invalid approved receipts are errors,
    # never silently accepted as merely unpriced.
    for snapshot in (before, after):
        proof = audit_boq(snapshot, require_pricebook=True)
        if (not proof.get("reconciled") or not proof.get("pricing_complete") or
            proof.get("numeric_source_status") != "EXACT_SOURCE_VERIFIED"):
            return None
    if b0.get("rows_by_code") != b1.get("rows_by_code"):
        return None

    def rows_by_identity(snapshot):
        indexed = {}
        for row in snapshot.get("boq") or []:
            ids = row.get("source_ids")
            # Aggregated BOQ rows cannot be attributed to one measured shape.
            if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str):
                return None
            key = (ids[0], row["item_code"], row["unit"])
            if key in indexed or key not in indexed_keys:
                return None
            qty = decimal_value(row.get("quantity"), field="approved boq quantity", non_negative=True)
            eff = decimal_value(row.get("effective_quantity", qty), field="effective quantity", non_negative=True)
            # Waste/allowance cannot be treated as linear quantity changes.
            if qty != eff or "factor" not in row:
                return None
            factor = decimal_value(row["factor"], field="approved factor", non_negative=True)
            rate = decimal_value(row.get("unit_price"), field="approved unit price", non_negative=True)
            if factor <= 0:
                return None
            indexed[key] = (qty, rate, factor, row.get("price_code"))
        return indexed

    old, new = rows_by_identity(before), rows_by_identity(after)
    if old is None or new is None:
        return None
    if set(old) != set(_indexed(before)) or set(new) != set(_indexed(after)):
        return None
    # For added/removed items, require that the same reviewed price-code
    # exists in both historical catalogs; no guessing a missing period rate.
    reviewed_rates = b0["rows_by_code"]
    amounts = []
    with localcontext() as ctx:
        ctx.prec = 512
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        try:
            for key in sorted(indexed_keys):
                left = old.get(key)
                right = new.get(key)
                anchor = right or left
                if anchor is None:
                    return None
                q, rate, factor, code = anchor
                if (not code or code not in reviewed_rates or
                    any((item[1], item[2], item[3]) != (rate, factor, code)
                        for item in (left, right) if item)):
                    return None
                q_before = left[0] if left else Decimal(0)
                q_after = right[0] if right else Decimal(0)
                amounts.append((q_after - q_before) * rate * factor)
        except DecimalException as exc:
            raise ValueError("دقت محاسبه اثر مالی قابل حفظ نیست") from exc
    return {"amount": str(exact_sum(amounts, field="verified financial delta")),
            "currency": currency,
            "pricebook_sha256": b0["sha256"],
            "basis": "unchanged_verified_pricebook_rates_and_factors; quantity_only",
            "status": "VERIFIED_QUANTITY_ONLY_EFFECT_NOT_PAYMENT_CERTIFICATE"}

def preview_revision_quantity_changes(service, *, project_id: str,
                                      before_version: int, after_version: int,
                                      include_verified_financial_impact: bool = False) -> dict:
    """Exact Decimal changes, never a fabricated financial impact."""
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("شناسه پروژه الزامی است")
    current = service.open_project(project_id)
    if not isinstance(current, dict):
        raise KeyError(project_id)
    if current.get("id") != project_id or type(current.get("_meta", {}).get("version")) is not int:
        raise ValueError("پروژه و نسخه جاری نامعتبر است")
    if after_version > current["_meta"]["version"]:
        raise ValueError("نسخه گزارش از نسخه جاری جدیدتر است")
    old, new = _historical(service, project_id, before_version, after_version)
    if type(include_verified_financial_impact) is not bool:
        raise ValueError("درخواست اثر مالی باید صریح باشد")
    left, right = _indexed(old), _indexed(new)
    if not left and not right:
        raise ValueError("هیچ ریزمتره تأییدشده‌ای برای مقایسه وجود ندارد")
    keys = sorted(set(left) | set(right))
    report_rows, totals = [], {}
    for row_no, key in enumerate(keys, 1):
        sid, code, unit = key
        prior = left.get(key)
        current_row = right.get(key)
        q_old = prior["quantity"] if prior else Decimal(0)
        q_new = current_row["quantity"] if current_row else Decimal(0)
        delta = q_new - q_old
        # Do not invent a price: a quantity revision report is not a pricebook
        # approval. The separate audited estimate pathway owns pricing.
        base = current_row or prior
        report_rows.append({
            "item_no": row_no,
            "item_code": code,
            "description": base["description"],
            "quantity": str(q_new),
            "unit": unit,
            "source_id": sid,
            "مقدار قبلی": str(q_old),
            "مقدار جدید": str(q_new),
            "اختلاف مقدار": str(delta),
            "وضعیت تغییر": ("افزوده" if prior is None else
                            "حذف‌شده" if current_row is None else
                            "تغییرکرده" if delta else "بدون تغییر"),
            "floor": base["floor"],
            "member": base["member"],
            "نسخه ریزمتره قبلی": prior["revision"] if prior else "وجود نداشت",
            "نسخه ریزمتره جدید": current_row["revision"] if current_row else "وجود ندارد",
            "notes": "اثر مالی قابل تعیین نیست؛ این گزارش، مقدارمحور و بدون نرخ تأییدشده است",
        })
        group = totals.setdefault(unit, [])
        group.append(delta)
    effect = (_verified_financial_effect(old, new, set(left) | set(right))
              if include_verified_financial_impact else None)
    if effect is not None:
        for row in report_rows:
            row["notes"] = "اثر مالی مقدارمحور فقط با نرخ و ضریب ثابت و منبع تأییدشده بررسی شده است"
    return {
        "project_id": project_id,
        "before_version": before_version,
        "after_version": after_version,
        "rows": report_rows,
        "delta_by_unit": {unit: str(exact_sum(values, field="delta")) for unit, values in sorted(totals.items())},
        "financial_impact": effect,
        "financial_impact_status": (effect["status"] if effect else "NOT_DETERMINABLE_WITHOUT_APPROVED_PRICES"),
        "status": "source_backed_historical_quantity_comparison_not_financial_approval",
        "readonly": True,
    }


def export_revision_quantity_package(
    service, *, project_id: str, before_version: int, after_version: int,
    expected_current_version: int, destination: str | Path,
    include_verified_financial_impact: bool = False,
) -> dict:
    """Atomic four-format package using original ProjectReport, and SHA manifest."""
    target = Path(destination)
    if target.exists() or any(p.is_symlink() for p in (target, *target.parents)):
        raise FileExistsError("مقصد موجود یا مسیر نمادین است")
    before_digest = service.store.current_digest(project_id)
    snapshot = service.open_project(project_id)
    if (not isinstance(snapshot, dict) or
        type(expected_current_version) is not int or
        snapshot["_meta"]["version"] != expected_current_version):
        raise ValueError("نسخه فعلی پروژه با درخواست مطابقت ندارد")
    result = preview_revision_quantity_changes(
        service, project_id=project_id, before_version=before_version,
        after_version=after_version,
        include_verified_financial_impact=include_verified_financial_impact,
    )
    report = build_report(
        snapshot["name"] + " | گزارش تغییرات ریزمتره",
        result["rows"], metadata={
            "project_id": project_id,
            "نسخه مبنا": before_version,
            "نسخه جدید": after_version,
            "نسخه جاری": expected_current_version,
            "وضعیت اثر مالی": result["financial_impact_status"],
            "نوع سند": "گزارش مقدارمحور با منشأ تاریخچه SQLite",
        },
    )
    if not report.validate()["valid"]:
        raise ValueError("اعتبارسنجی ردیف گزارش تغییرات ناموفق بود")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix="structuralpro_p7_p4_") as folder:
        stage = Path(folder) / "package"
        stage.mkdir()
        files = [
            report.export(stage / ("revision_changes." + fmt), fmt)
            for fmt in ("pdf", "xlsx", "docx", "csv")
        ]
        payload = {
            **build_bundle_manifest(files, project_id=project_id, revision=str(after_version)),
            "schema": "structuralpro.phase7.technical-office-revision-bundle.v1",
            "before_version": before_version, "after_version": after_version,
            "expected_current_version": expected_current_version,
            "source_project_digest": before_digest,
            "delta_by_unit": result["delta_by_unit"],
            "financial_impact": result["financial_impact"],
            "financial_impact_status": result["financial_impact_status"],
            "status": result["status"],
            "readonly": True,
        }
        (stage / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        # Re-query original stored revisions and all physical drawing sources.
        if (service.store.current_digest(project_id) != before_digest or
            service.open_project(project_id) != snapshot):
            raise RuntimeError("پروژه هنگام تهیه گزارش تغییر کرده است")
        again = preview_revision_quantity_changes(
            service, project_id=project_id, before_version=before_version,
            after_version=after_version,
            include_verified_financial_impact=include_verified_financial_impact,
        )
        if again != result or service.store.current_digest(project_id) != before_digest:
            raise RuntimeError("تاریخچه یا منبع گزارش تغییر کرده است")
        if target.exists():
            raise FileExistsError("مسیر مقصد هنگام صدور ایجاد شده است")
        os.rename(stage, target)
    return {"destination": str(target), "manifest": payload}
