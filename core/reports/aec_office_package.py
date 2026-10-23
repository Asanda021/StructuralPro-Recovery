"""Strict, source-traceable Persian quantity/estimate/statement office exports.

Uses the existing StructuralPro XLSX/PDF exporters and project BOQ. Never turns
missing unit prices into a zero-priced estimate or fabricates a statement.
"""
from __future__ import annotations
from core.commercial.exact_values import number,wire,exact

import math
import hashlib
from pathlib import Path
from typing import Any, Iterable

from core.takeoff.boq import validate_boq_structure
from core.takeoff.units import normalize_unit
from core.takeoff.commit_guards import _is_payable_quantity
from core.reports.exporters import export_xlsx, export_pdf


TAKEOFF_COLS = (
    ("floor", "طبقه / بخش"), ("source_id", "شناسه منبع"),
    ("member", "عضو / سیستم"), ("item_code", "کد عملیات"),
    ("description", "شرح ریزمتره"), ("quantity", "مقدار"),
    ("unit", "واحد"), ("formula", "مبنای محاسبه"),
    ("revision", "نسخه"), ("provenance", "مرجع"),
)
ESTIMATE_COLS = (
    ("item_code", "کد عملیات"), ("price_code", "کد فهرست‌بها"),
    ("description", "شرح"), ("quantity", "مقدار"),
    ("unit", "واحد"), ("unit_price", "بهای واحد"),
    ("factor", "ضریب"), ("total", "مبلغ کل"),
    ("source_ids", "منابع ریزمتره"),
)
STATEMENT_COLS = (
    ("item_code", "ردیف"), ("description", "شرح"), ("unit", "واحد"),
    ("quantity", "مقدار این دوره"), ("unit_price", "بهای واحد"),
    ("total", "مبلغ این دوره"), ("source_id", "مرجع صورت‌وضعیت"),
)


def finite_quantity(value: Any, title: str, *, zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{title}: عدد معتبر لازم است")
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{title}: عدد معتبر لازم است") from exc
    if not math.isfinite(v) or v < 0 or (v == 0 and not zero):
        raise ValueError(f"{title}: مقدار مثبت و متناهی لازم است")
    return v


def _required_text(value: Any, title: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{title} الزامی است")
    return value.strip()


def flatten_takeoffs(project: dict) -> list[dict]:
    rows = []
    unique = set()
    for record in project.get("takeoffs") or []:
        if not isinstance(record, dict):
            raise ValueError("ساختار رکورد متره نامعتبر است")
        sid = _required_text(record.get("source_id"), "منبع متره")
        if sid in unique:
            raise ValueError("منبع متره تکراری است")
        unique.add(sid)
        quantities = record.get("quantities")
        if not isinstance(quantities, list) or not quantities:
            raise ValueError("ریزکمیت‌های متره ناقص‌اند")
        for i, item in enumerate(quantities, 1):
            if not isinstance(item, dict):
                raise ValueError("ریزکمیت نامعتبر است")
            quantity = wire(number(item.get("amount"), "کمیت ریزمتره"))
            unit = normalize_unit(_required_text(item.get("unit"), "واحد ریزمتره"))
            rows.append({
                "source_id": sid, "floor": record.get("system", ""),
                "member": record.get("member_code", ""),
                "item_code": _required_text(item.get("code"), "کد عملیات"),
                "description": _required_text(item.get("title"), "شرح عملیات"),
                "quantity": quantity, "unit": unit,
                "formula": _required_text(item.get("formula"), "فرمول"),
                "revision": record.get("revision", ""),
                "provenance": str((record.get("provenance") or {}).get("source_id", sid)),
            })
    return rows


@exact
def audit_boq(project: dict, *, require_pricebook: bool = False) -> dict:
    """Reconcile every BOQ source-group quantity to its original takeoff rows."""
    from core.takeoff.manual_formula_amendments import effective_takeoffs
    effective = effective_takeoffs(project, project.get("takeoffs") or [])
    details = flatten_takeoffs({**project, "takeoffs": effective})
    boq = project.get("boq") or []
    result = validate_boq_structure(boq)
    if not result["valid"]:
        raise ValueError("ساختار ردیف‌های برآورد نامعتبر است")
    pricebook = None
    price_rows = {}
    if require_pricebook:
        pricebook = project.get("user_pricebook_review")
        if not isinstance(pricebook, dict) or pricebook.get("status") != "approved":
            raise ValueError("فهرست‌بهای واردشده توسط کاربر باید بازبینی و تأیید شده باشد")
        _required_text(pricebook.get("approved_by"), "تأییدکننده فهرست‌بها")
        raw_path = Path(_required_text(pricebook.get("path"), "مسیر فایل واردشده"))
        if not raw_path.is_file():
            raise ValueError("فایل مبنای فهرست‌بها در دسترس نیست")
        digest = _required_text(pricebook.get("sha256"), "اثر انگشت فهرست‌بها")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("SHA-256 فهرست‌بها معتبر نیست")
        actual_hash = hashlib.sha256()
        with raw_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                actual_hash.update(chunk)
        if actual_hash.hexdigest() != digest.lower():
            raise ValueError("محتوای فایل فهرست‌بها تغییر کرده است")
        price_rows = pricebook.get("rows_by_code")
        if not isinstance(price_rows, dict) or not price_rows:
            raise ValueError("ردیف‌های قیمت تأییدشده در فهرست‌بها موجود نیستند")
    exact_source=False
    if require_pricebook:
        from core.pricing.import_service import verify_reviewed_rates
        exact_source=verify_reviewed_rates(raw_path,pricebook)
    payable_sources = {(r["source_id"],q["code"],normalize_unit(q["unit"])) for r in effective for q in r.get("quantities", []) if _is_payable_quantity(r,q)}
    expected = {}
    for row in details:
        if (row["source_id"],row["item_code"],row["unit"]) not in payable_sources: continue
        key = (row["source_id"], row["item_code"], row["unit"])
        expected[key] = expected.get(key, number(0,"جمع")) + number(row["quantity"],"کمیت")
    actual = {}
    unpriced = []
    for n, row in enumerate(boq, 1):
        if not isinstance(row, dict):
            raise ValueError("ردیف برآورد نامعتبر است")
        code = _required_text(row.get("item_code"), "کد عملیات برآورد")
        unit = normalize_unit(_required_text(row.get("unit"), "واحد برآورد"))
        amount = number(row.get("quantity"), "کمیت برآورد")
        source_ids = row.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            raw = row.get("source_id")
            source_ids = [raw] if raw else []
        if not source_ids:
            raise ValueError("منابع ردیف برآورد ثبت نشده‌اند")
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("منابع تکراری در یک ردیف برآورد")
        matching = [key for key in expected if key[0] in source_ids
                    and key[1] == code and key[2] == unit]
        if not matching:
            raise ValueError("کد، واحد یا منبع ردیف برآورد با ریزمتره تطبیق ندارد")
        expected_total = sum((expected[k] for k in matching), number(0,"جمع"))
        if expected_total != amount:
            raise ValueError("جمع کمیت ردیف BOQ با ریزمتره اصلی یکسان نیست")
        for key in matching:
            if key in actual:
                raise ValueError("یک منبع ریزمتره در چند ردیف BOQ شمارش شده است")
            actual[key] = expected[key]
        if row.get("unit_price") is None or not row.get("price_code"):
            unpriced.append(n)
        elif require_pricebook:
            price = number(row["unit_price"], "قیمت واحد")
            price_origin = price_rows.get(row["price_code"])
            if not isinstance(price_origin, dict):
                raise ValueError("کد قیمت با فهرست‌بهای تأییدشده تطبیق ندارد")
            if normalize_unit(_required_text(price_origin.get("unit"), "واحد قیمت")) != unit:
                raise ValueError("واحد ردیف قیمت با BOQ مطابقت ندارد")
            expected_price = number(price_origin.get("unit_price"), "بهای واحد مستند")
            if price != expected_price:
                raise ValueError("قیمت واحد BOQ با فهرست‌بهای واردشده برابر نیست")
            if pricebook.get('numeric_encoding_version')==2:
                factor=number(row.get('factor',1),'ضریب');effective=number(row.get('effective_quantity',amount),'مقدار مؤثر')
                total=number(row.get('total'),'مبلغ ردیف')
                if total!=effective*price*factor:raise ValueError('مبلغ ردیف برآورد با مقدار، ضریب و قیمت واحد ناسازگار است')
            else:
                # Keep the declared tolerance of previously stored legacy totals.
                factor=finite_quantity(row.get('factor',1),'ضریب',zero=True)
                effective=finite_quantity(row.get('effective_quantity',amount),'مقدار مؤثر',zero=True)
                total=finite_quantity(row.get('total'),'مبلغ ردیف',zero=True)
                if not math.isclose(total,effective*float(price)*factor,rel_tol=1e-9,abs_tol=1e-6):
                    raise ValueError('مبلغ ردیف برآورد با مقدار، ضریب و قیمت واحد ناسازگار است')
    if set(expected) != set(actual):
        raise ValueError("برخی ریزمتره‌های پروژه در BOQ موجود نیستند")
    if require_pricebook and unpriced:
        raise ValueError("برای برآورد مالی، فهرست‌بهای واردشده و کد/قیمت همه ردیف‌ها الزامی است")
    return {"takeoff_count": len(details), "boq_count": len(boq),
            "unpriced_item_numbers": unpriced, "pricing_complete": not unpriced,
            "reconciled": True, "numeric_source_status": "EXACT_SOURCE_VERIFIED" if exact_source else "LEGACY_EXPLICIT_REVIEW_ONLY"}


def prepare_office_rows(project: dict, mode: str, *, statement: dict | None = None) -> tuple[list[dict], tuple, dict]:
    pid = _required_text(project.get("id"), "شناسه پروژه")
    report = audit_boq(project, require_pricebook=(mode == "estimate"))
    metadata = {"پروژه": pid, "وضعیت کنترل": "تطبیق با ریزمتره",
                "تعداد اقلام بدون قیمت": len(report["unpriced_item_numbers"])}
    if mode == "takeoff":
        return flatten_takeoffs(project), TAKEOFF_COLS, metadata
    if mode == "estimate":
        rows = []
        for row in project.get("boq") or []:
            rows.append({"item_code": row["item_code"], "price_code": row["price_code"],
                         "description": row["description"], "quantity": row["quantity"],
                         "unit": row["unit"], "unit_price": row["unit_price"],
                         "factor": row.get("factor", 1), "total": row["total"],
                         "source_ids": "، ".join(row.get("source_ids") or [row.get("source_id", "")])})
        return rows, ESTIMATE_COLS, metadata
    if mode == "statement":
        if not isinstance(statement, dict) or statement.get("status") != "approved":
            raise ValueError("صورت‌وضعیت باید تأیید و مستند شده باشد")
        _required_text(statement.get("period_id"), "شماره دوره صورت‌وضعیت")
        _required_text(statement.get("approved_by"), "تأییدکننده صورت‌وضعیت")
        lines = statement.get("rows")
        if not isinstance(lines, list) or not lines:
            raise ValueError("ردیف‌های صورت‌وضعیت مستند نیستند")
        previous = statement.get("previous_quantities_by_source")
        if not isinstance(previous, dict):
            raise ValueError("مقادیر تأییدشده دوره‌های قبلی باید صریح مشخص شوند")
        takeoff_index = {(x["source_id"], x["item_code"], x["unit"]): x["quantity"]
                         for x in flatten_takeoffs(project)}
        rows = []
        seen = set()
        for row in lines:
            sid = _required_text(row.get("source_id"), "مرجع صورت‌وضعیت")
            if sid in seen:
                raise ValueError("مرجع صورت‌وضعیت تکراری است")
            seen.add(sid)
            q = finite_quantity(row.get("quantity"), "مقدار دوره")
            code = _required_text(row.get("item_code"), "کد ردیف")
            unit = normalize_unit(_required_text(row.get("unit"), "واحد"))
            permitted = takeoff_index.get((sid, code, unit))
            if permitted is None:
                raise ValueError("ردیف صورت‌وضعیت به ریزمتره پروژه متصل نیست")
            previous_amount = finite_quantity(previous.get(sid, 0), "مقدار قبلی", zero=True)
            if q + previous_amount > permitted + 1e-9:
                raise ValueError("مقدار تجمعی صورت‌وضعیت از ریزمتره تأییدشده بیشتر است")
            price = finite_quantity(row.get("unit_price"), "بهای واحد دوره", zero=True)
            total = finite_quantity(row.get("total"), "مبلغ دوره", zero=True)
            if not math.isclose(total, q * price, rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("مبلغ دوره با قیمت و مقدار تأییدشده برابر نیست")
            rows.append({"source_id": sid, "item_code": code,
                         "description": _required_text(row.get("description"), "شرح صورت‌وضعیت"),
                         "quantity": q, "unit": unit,
                         "unit_price": price, "total": total})
        metadata["دوره"] = statement["period_id"]
        metadata["تأییدکننده"] = statement["approved_by"]
        return rows, STATEMENT_COLS, metadata
    raise ValueError("نوع گزارش باید ریزمتره، برآورد یا صورت‌وضعیت باشد")


def export_office_package(project: dict, mode: str, fmt: str, path: str | Path,
                          *, statement: dict | None = None) -> Path:
    rows, columns, metadata = prepare_office_rows(project, mode, statement=statement)
    if not rows:
        raise ValueError("گزارش خالی است؛ خروجی حرفه‌ای تولید نمی‌شود")
    titles = {"takeoff": "ریزمتره مستند", "estimate": "برآورد تأییدشده",
              "statement": "صورت‌وضعیت تأییدشده"}
    if fmt == "xlsx":
        return export_xlsx(rows, path, title=titles[mode], metadata=metadata, columns=columns)
    if fmt == "pdf":
        return export_pdf(rows, path, title=titles[mode], metadata=metadata, columns=columns)
    raise ValueError("فرمت خروجی فقط Excel یا PDF است")
