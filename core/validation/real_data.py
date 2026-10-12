"""Real-project data validation for StructuralPro.

This layer validates persisted project data and drawing/takeoff candidates without
performing structural design checks. It focuses on data quality, traceability,
units, finite/non-negative quantities, duplicate sources/codes, and cross-stage
consistency.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Iterable


_LENGTH_UNITS = {"m", "cm", "mm", "km", "ft", "in"}
_AREA_UNITS = {"m2", "cm2", "mm2", "ft2"}
_VOLUME_UNITS = {"m3", "cm3", "mm3", "ft3"}
_MASS_UNITS = {"kg", "g", "t"}
_COUNT_UNITS = {"عدد", "count", "pcs"}
_ALLOWED_UNITS = _LENGTH_UNITS | _AREA_UNITS | _VOLUME_UNITS | _MASS_UNITS | _COUNT_UNITS | {"", "ریال", "تومان"}


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _number(value: Any, path: str, issues: list[ValidationIssue], *, non_negative: bool = True) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        issues.append(ValidationIssue("error", "invalid_number", path, "مقدار عددی معتبر نیست"))
        return None
    if not math.isfinite(value):
        issues.append(ValidationIssue("error", "non_finite", path, "مقدار باید متناهی باشد"))
        return None
    if non_negative and value < 0:
        issues.append(ValidationIssue("error", "negative_quantity", path, "مقدار نمی‌تواند منفی باشد"))
        return None
    return value


def _unit(unit: Any, path: str, issues: list[ValidationIssue]) -> str:
    value = str(unit or "").strip()
    if value not in _ALLOWED_UNITS:
        issues.append(ValidationIssue("error", "unknown_unit", path, f"واحد ناشناخته: {value}"))
    return value


def _duplicates(values: Iterable[Any]) -> set[str]:
    seen: set[str] = set()
    dup: set[str] = set()
    for value in values:
        key = str(value or "").strip()
        if not key:
            continue
        if key in seen:
            dup.add(key)
        seen.add(key)
    return dup


def validate_takeoffs(rows: Iterable[dict[str, Any]], prefix: str = "takeoffs") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rows = list(rows)
    ids = [row.get("id") for row in rows]
    for value in _duplicates(ids):
        issues.append(ValidationIssue("error", "duplicate_id", prefix, f"شناسه متره تکراری است: {value}"))
    sources = [row.get("source_id") or row.get("source") for row in rows]
    for value in _duplicates(sources):
        issues.append(ValidationIssue("error", "duplicate_source", prefix, f"منبع متره تکراری است: {value}"))

    for i, row in enumerate(rows):
        path = f"{prefix}[{i}]"
        if not str(row.get("description") or row.get("item") or row.get("member_code") or "").strip():
            issues.append(ValidationIssue("error", "missing_description", path, "شرح متره خالی است"))
        quantities = row.get("quantities")
        if isinstance(quantities, list):
            if not quantities:
                issues.append(ValidationIssue("error", "empty_quantities", path, "متره بدون مقدار است"))
            for j, q in enumerate(quantities):
                qpath = f"{path}.quantities[{j}]"
                _number(q.get("amount", q.get("quantity")), f"{qpath}.amount", issues)
                _unit(q.get("unit"), f"{qpath}.unit", issues)
        else:
            _number(row.get("quantity"), f"{path}.quantity", issues)
            _unit(row.get("unit"), f"{path}.unit", issues)
    return issues


def validate_boq(rows: Iterable[dict[str, Any]], takeoff_sources: set[str] | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    rows = list(rows)
    codes = [row.get("price_code") or row.get("code") for row in rows]
    for value in _duplicates(codes):
        issues.append(ValidationIssue("warning", "duplicate_boq_code", "boq", f"کد BOQ تکراری است: {value}"))
    for i, row in enumerate(rows):
        path = f"boq[{i}]"
        quantity = _number(row.get("quantity"), f"{path}.quantity", issues)
        _unit(row.get("unit"), f"{path}.unit", issues)
        if not str(row.get("description") or "").strip():
            issues.append(ValidationIssue("error", "missing_description", path, "شرح ردیف BOQ خالی است"))
        if "unit_price" in row and row.get("unit_price") not in (None, ""):
            _number(row.get("unit_price"), f"{path}.unit_price", issues)
        source = str(row.get("source") or "").strip()
        if takeoff_sources is not None and source and source not in takeoff_sources:
            issues.append(ValidationIssue("warning", "orphan_source", f"{path}.source", "منبع BOQ به متره موجود متصل نیست"))
        if quantity is not None and quantity == 0:
            issues.append(ValidationIssue("warning", "zero_quantity", f"{path}.quantity", "مقدار BOQ صفر است"))
    return issues


def validate_estimate(estimate: dict[str, Any] | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if estimate is None:
        return issues
    cost = estimate.get("cost", {})
    if not isinstance(cost, dict):
        issues.append(ValidationIssue("error", "invalid_estimate_cost", "estimate.cost", "ساختار هزینه برآورد معتبر نیست"))
        return issues
    for key, value in cost.items():
        if isinstance(value, (int, float, str)) and key not in {"currency"}:
            _number(value, f"estimate.cost.{key}", issues)
    return issues


def validate_finance(project: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    collections = (
        ("commitment_entries", "تعهد"),
        ("cost_entries", "هزینه"),
        ("receipt_entries", "دریافتی"),
        ("financial_documents", "سند مالی"),
    )
    for collection, label in collections:
        rows = project.get(collection, [])
        if not isinstance(rows, list):
            issues.append(ValidationIssue("error", "invalid_collection", collection, f"ساختار {label} معتبر نیست"))
            continue
        ids = [x.get("id") for x in rows if isinstance(x, dict)]
        for value in _duplicates(ids):
            issues.append(ValidationIssue("error", "duplicate_finance_id", collection, f"شناسه تکراری: {value}"))
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append(ValidationIssue("error", "invalid_row", f"{collection}[{i}]", "رکورد معتبر نیست"))
                continue
            _number(row.get("amount", 0), f"{collection}[{i}].amount", issues)
            for key in ("paid_amount",):
                if key in row:
                    _number(row.get(key), f"{collection}[{i}].{key}", issues)
    valid_ids = {
        collection: {int(x.get("id", 0)) for x in project.get(collection, []) if isinstance(x, dict)}
        for collection, _ in collections
    }
    for i, doc in enumerate(project.get("financial_documents", [])):
        if not isinstance(doc, dict):
            continue
        for field, collection in (
            ("commitment_id", "commitment_entries"),
            ("cost_entry_id", "cost_entries"),
            ("receipt_id", "receipt_entries"),
        ):
            ref = doc.get(field)
            if ref is not None:
                try:
                    ref_id = int(ref)
                except (TypeError, ValueError):
                    issues.append(ValidationIssue("error", "invalid_reference", f"financial_documents[{i}].{field}", "شناسه ارجاع معتبر نیست"))
                    continue
                if ref_id not in valid_ids[collection]:
                    issues.append(ValidationIssue("error", "broken_reference", f"financial_documents[{i}].{field}", "ارجاع به رکورد موجود نیست"))
    return issues


def validate_drawing_candidates(inspection: dict[str, Any] | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if inspection is None:
        return issues
    candidates = inspection.get("candidates", [])
    if not isinstance(candidates, list):
        issues.append(ValidationIssue("error", "invalid_candidates", "drawing.candidates", "ساختار کاندیداهای نقشه معتبر نیست"))
        return issues
    sources = []
    for i, row in enumerate(candidates):
        path = f"drawing.candidates[{i}]"
        if not isinstance(row, dict):
            issues.append(ValidationIssue("error", "invalid_candidate", path, "کاندیدای نقشه معتبر نیست"))
            continue
        sources.append(row.get("source"))
        _number(row.get("quantity"), f"{path}.quantity", issues)
        _unit(row.get("unit"), f"{path}.unit", issues)
        if not str(row.get("description") or "").strip():
            issues.append(ValidationIssue("warning", "missing_candidate_description", path, "شرح کاندیدای نقشه خالی است"))
    for value in _duplicates(sources):
        issues.append(ValidationIssue("error", "duplicate_drawing_source", "drawing.candidates", f"منبع نقشه تکراری است: {value}"))
    return issues


def validate_project(project: dict[str, Any]) -> dict[str, Any]:
    """Run all deterministic real-data gates for one persisted project."""
    issues: list[ValidationIssue] = []
    if not isinstance(project, dict):
        return {
            "valid": False, "status": "invalid", "score": 0,
            "issues": [ValidationIssue("error", "invalid_project", "project", "ساختار پروژه معتبر نیست").to_dict()],
            "counts": {"errors": 1, "warnings": 0},
        }

    if not str(project.get("id") or "").strip():
        issues.append(ValidationIssue("error", "missing_project_id", "id", "شناسه پروژه خالی است"))
    if not str(project.get("name") or "").strip():
        issues.append(ValidationIssue("warning", "missing_project_name", "name", "نام پروژه خالی است"))

    takeoffs = project.get("takeoffs", [])
    takeoff_sources = {
        str(x.get("source_id") or x.get("source") or "").strip()
        for x in takeoffs if isinstance(x, dict)
    }
    takeoff_sources.discard("")
    issues.extend(validate_takeoffs(takeoffs))
    issues.extend(validate_boq(project.get("boq", []), takeoff_sources))
    issues.extend(validate_estimate(project.get("estimate")))
    issues.extend(validate_finance(project))

    total = max(len(issues), 1)
    errors = sum(x.severity == "error" for x in issues)
    warnings = sum(x.severity == "warning" for x in issues)
    score = max(0, round(100 - (errors * 20 + warnings * 5)))
    return {
        "valid": errors == 0,
        "status": "valid" if errors == 0 else "invalid",
        "score": score,
        "issues": [x.to_dict() for x in issues],
        "counts": {"errors": errors, "warnings": warnings},
        "checked": {
            "takeoffs": len(takeoffs) if isinstance(takeoffs, list) else 0,
            "boq": len(project.get("boq", [])) if isinstance(project.get("boq", []), list) else 0,
            "financial_documents": len(project.get("financial_documents", [])) if isinstance(project.get("financial_documents", []), list) else 0,
        },
    }
