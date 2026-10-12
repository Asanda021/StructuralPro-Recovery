"""Validated bridge from graphical drawing sessions to persistent takeoff/BOQ rows.

The bridge is intentionally deterministic: it never invents scale, quantities, or
price data. Callers must validate the session and explicitly select rows to commit.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.graphical_takeoff import Point, polygon_area, polyline_length


_KIND_UNITS = {"length": "m", "area": "m2", "count": "عدد"}


def validate_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a serialized session and return a compact, user-readable report."""
    issues: list[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "issues": ["داده نشست متره باید یک شیء معتبر باشد"]}
    try:
        session = DrawingTakeoffSession.from_dict(payload)
        report = session.validate()
        issues.extend(report.get("issues", []))
        if not str(session.drawing_source).strip():
            issues.append("مسیر/شناسه منبع نقشه ثبت نشده است")
        for item in session.items:
            if item.kind not in _KIND_UNITS:
                issues.append(f"نوع متره {item.id} پشتیبانی نمی‌شود")
            elif item.unit != _KIND_UNITS[item.kind]:
                issues.append(f"واحد متره {item.id} با نوع آن سازگار نیست")
            expected_ref = f"{session.drawing_source}#page={item.page}&takeoff={item.id}"
            if not item.source_ref.strip() or item.source_ref != expected_ref:
                issues.append(f"مرجع صفحه/ناحیه برای متره {item.id} با منبع ذخیره‌شده مطابقت ندارد")
            if item.kind in {"length", "area"} and not item.formula.strip():
                issues.append(f"فرمول اندازه‌گیری متره {item.id} ثبت نشده است")
            if item.kind == "length" and len(item.geometry) < 2:
                issues.append(f"هندسه متره طول {item.id} ناقص است")
            if item.kind == "area" and len(item.geometry) < 3:
                issues.append(f"هندسه متره مساحت {item.id} ناقص است")
            for point in item.geometry:
                if len(point) != 2 or any(not math.isfinite(float(value)) for value in point):
                    issues.append(f"مختصات هندسه متره {item.id} نامعتبر است")
                    break
            if item.kind == "count" and (item.quantity <= 0 or not float(item.quantity).is_integer()):
                issues.append(f"تعداد متره {item.id} باید عدد صحیح مثبت باشد")
            if item.kind in {"length", "area"} and item.page in session.calibrations:
                factor = session.calibrations[item.page].meters_per_pixel
                points = [Point(*point) for point in item.geometry]
                if item.kind == "length":
                    expected = polyline_length(points) * factor
                else:
                    holes = [[Point(*point) for point in hole] for hole in item.holes]
                    if any(len(hole) < 3 for hole in holes):
                        issues.append(f"هندسه بازشو متره {item.id} ناقص است")
                    net = polygon_area(points) - sum(polygon_area(hole) for hole in holes)
                    expected = net * factor * factor
                if expected <= 0 or not math.isclose(item.quantity, expected, rel_tol=1e-9, abs_tol=1e-9):
                    issues.append(f"مقدار متره {item.id} با هندسه و کالیبراسیون ثبت‌شده مطابقت ندارد")
    except Exception as exc:
        issues.append(f"نشست متره قابل بازیابی/اعتبارسنجی نیست: {exc}")
    return {"valid": not issues, "issues": list(dict.fromkeys(issues))}


def session_to_boq_rows(
    payload: dict[str, Any],
    *,
    session_id: str,
    selected_item_ids: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert only explicitly selected, validated drawing items into BOQ inputs."""
    report = validate_session_payload(payload)
    if not report["valid"]:
        raise ValueError("نشست نقشه معتبر نیست: " + "؛ ".join(report["issues"]))
    session = DrawingTakeoffSession.from_dict(payload)
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("شناسه پایدار نشست نقشه الزامی است")
    selected = None if selected_item_ids is None else {str(x) for x in selected_item_ids}
    if selected is not None and not selected:
        raise ValueError("برای انتقال به BOQ باید دست‌کم یک متره صریحاً انتخاب شود")
    known = {item.id for item in session.items}
    if selected is not None:
        unknown = selected - known
        if unknown:
            raise ValueError("شناسه متره در نشست وجود ندارد: " + "، ".join(sorted(unknown)))
    rows: list[dict[str, Any]] = []
    for item in session.items:
        if selected is not None and item.id not in selected:
            continue
        if item.quantity <= 0:
            raise ValueError(f"مقدار متره {item.id} باید برای ورود به BOQ مثبت باشد")
        rows.append({
            "takeoff_id": item.id,
            "source_id": f"drawing:{sid}:{item.id}",
            "source": item.source_ref,
            "source_type": "drawing_takeoff",
            "drawing_source": session.drawing_source,
            "page": item.page,
            "kind": item.kind,
            "description": item.label.strip() or item.takeoff_code.strip() or item.kind,
            "quantity": float(item.quantity),
            "unit": item.unit,
            "item_code": item.takeoff_code.strip() or f"DRAW-{item.kind.upper()}",
            "price_code": item.takeoff_code.strip() or None,
            "unit_price": None,
            "formula": item.formula,
            "geometry": [list(point) for point in item.geometry],
            "holes": [[list(point) for point in hole] for hole in item.holes],
            "confidence": float(item.confidence),
            "needs_confirmation": False,
        })
    if not rows:
        raise ValueError("هیچ متره‌ای برای انتقال به BOQ انتخاب نشده است")
    return rows


def build_takeoff_export_payload(session: DrawingTakeoffSession) -> dict[str, Any]:
    """Export a review handoff through the same validator used by project storage."""
    source = str(session.drawing_source).strip()
    validated = session_to_boq_rows(
        session.to_dict(), session_id=source,
        selected_item_ids=[item.id for item in session.items],
    )
    items_by_id = {item.id: item for item in session.items}
    rows = [{
        "source_id": f"drawing:{source}:page:{row['page']}:{row['takeoff_id']}",
        "source_ref": row["source"], "page": row["page"], "kind": row["kind"],
        "quantity": row["quantity"], "unit": row["unit"],
        "description": row["description"], "formula": row["formula"],
        "takeoff_code": items_by_id[row["takeoff_id"]].takeoff_code,
        "status": "needs_review",
    } for row in validated]
    return {
        "schema": "structuralpro.drawing-takeoff.v1",
        "drawing_source": source, "approval_required": True, "items": rows,
        "summary": {
            "items": len(rows), "needs_review": len(rows),
            "by_unit": {
                unit: sum(row["quantity"] for row in rows if row["unit"] == unit)
                for unit in sorted({row["unit"] for row in rows})
            },
        },
    }
