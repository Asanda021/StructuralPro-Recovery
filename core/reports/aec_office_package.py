"""Strict, source-traceable Persian quantity/estimate/statement office exports.

Uses the existing StructuralPro XLSX/PDF exporters and project BOQ. Never turns
missing unit prices into a zero-priced estimate or fabricates a statement.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from core.takeoff.boq import validate_boq_structure
from core.takeoff.units import normalize_unit
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
            quantity = finite_quantity(item.get("amount"), "کمیت ریزمتره", zero=True)
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


def audit_boq(project: dict, *, require_pricebook: bool = False) -> dict:
    """Reconcile every BOQ source-group quantity to its original takeoff rows."""
    details = flatten_takeoffs(project)
    boq = project.get("boq") or []
    result = validate_boq_structure(boq)
    if not result["valid"]:
        raise ValueError("ساختار ردیف‌های برآورد نامعتبر است")
    expected = {}
    for row in details:
        key = (row["source_id"], row["item_code"], row["unit"])
        expected[key] = expected.get(key, 0.0) + row["quantity"]
    actual = {}
    unpriced = []
    for n, row in enumerate(boq, 1):
        if not isinstance(row, dict):
            raise ValueError("ردیف برآورد نامعتبر است")
        code = _required_text(row.get("item_code"), "کد عملیات برآورد")
        unit = normalize_unit(_required_text(row.get("unit"), "واحد برآورد"))
        amount = finite_quantity(row.get("quantity"), "کمیت برآورد", zero=True)
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
        expected_total = math.fsum(expected[k] for k in matching)
        if not math.isclose(expected_total, amount, rel_tol=1e-9, abs_tol=1e-8):
            raise ValueError("جمع کمیت ردیف BOQ با ریزمتره اصلی یکسان نیست")
        for key in matching:
            if key in actual:
                raise ValueError("یک منبع ریزمتره در چند ردیف BOQ شمارش شده است")
            actual[key] = expected[key]
        if row.get("unit_price") is None or not row.get("price_code"):
            unpriced.append(n)
        elif require_pricebook:
            price = finite_quantity(row["unit_price"], "قیمت واحد", zero=True)
            factor = finite_quantity(row.get("factor", 1), "ضریب", zero=True)
            effective = finite_quantity(row.get("effective_quantity", amount), "مقدار مؤثر", zero=True)
            total = finite_quantity(row.get("total"), "مبلغ ردیف", zero=True)
            if not math.isclose(total, effective * price * factor, rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("مبلغ ردیف برآورد با مقدار، ضریب و قیمت واحد ناسازگار است")
    if set(expected) != set(actual):
        raise ValueError("برخی ریزمتره‌های پروژه در BOQ موجود نیستند")
    if require_pricebook and unpriced:
        raise ValueError("برای برآورد مالی، فهرست‌بهای واردشده و کد/قیمت همه ردیف‌ها الزامی است")
    return {"takeoff_count": len(details), "boq_count": len(boq),
            "unpriced_item_numbers": unpriced, "pricing_complete": not unpriced,
            "reconciled": True}


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
        rows = []
        seen = set()
        for row in lines:
            sid = _required_text(row.get("source_id"), "مرجع صورت‌وضعیت")
            if sid in seen:
                raise ValueError("مرجع صورت‌وضعیت تکراری است")
            seen.add(sid)
            q = finite_quantity(row.get("quantity"), "مقدار دوره")
            price = finite_quantity(row.get("unit_price"), "بهای واحد دوره", zero=True)
            total = finite_quantity(row.get("total"), "مبلغ دوره", zero=True)
            if not math.isclose(total, q * price, rel_tol=1e-9, abs_tol=1e-6):
                raise ValueError("مبلغ دوره با قیمت و مقدار تأییدشده برابر نیست")
            rows.append({"source_id": sid,
                         "item_code": _required_text(row.get("item_code"), "کد ردیف"),
                         "description": _required_text(row.get("description"), "شرح صورت‌وضعیت"),
                         "quantity": q, "unit": normalize_unit(_required_text(row.get("unit"), "واحد")),
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
