"""Integrity gates for the canonical Project -> Takeoff -> BOQ pipeline."""
from __future__ import annotations
import math
from typing import Any, Iterable
from .units import normalize_unit, convert
from .boq import build_boq, boq_summary
from .estimate import build_estimate

def normalize_takeoff_rows(rows: Iterable[dict[str, Any]], *, project_id: str = "") -> list[dict[str, Any]]:
    out, seen_ids, seen_sources = [], set(), set()
    for index, raw in enumerate(rows, 1):
        row = dict(raw)
        row_id = str(row.get("id") or f"T{index:04d}")
        if row_id in seen_ids:
            raise ValueError(f"شناسه متره تکراری: {row_id}")
        seen_ids.add(row_id)
        source_id = str(row.get("source_id") or "").strip()
        if source_id:
            if source_id in seen_sources:
                raise ValueError(f"منبع متره تکراری و مستعد دوباره‌شماری: {source_id}")
            seen_sources.add(source_id)
        try:
            quantity = float(row.get("quantity", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"مقدار متره نامعتبر در ردیف {row_id}") from exc
        if not math.isfinite(quantity) or quantity < 0:
            raise ValueError(f"مقدار متره باید متناهی و غیرمنفی باشد: {row_id}")
        unit = normalize_unit(row.get("unit", ""))
        price = row.get("unit_price")
        if price is not None:
            price = float(price)
            if not math.isfinite(price) or price < 0:
                raise ValueError(f"قیمت واحد نامعتبر: {row_id}")
        x = {
            **row, "id": row_id, "project_id": project_id or row.get("project_id", ""),
            "quantity": quantity, "unit": unit, "source_id": source_id,
        }
        if price is not None:
            x["unit_price"] = price
        out.append(x)
    return out

def build_core_pipeline(project: dict[str, Any], takeoff_rows: Iterable[dict[str, Any]], *,
                        price_catalog=None, year: int | None = None,
                        factors: dict[str, float] | None = None) -> dict[str, Any]:
    project_id = str(project.get("id") or "").strip()
    project_name = str(project.get("name") or "").strip()
    if not project_id or not project_name:
        raise ValueError("شناسه و نام پروژه الزامی است")
    rows = normalize_takeoff_rows(takeoff_rows, project_id=project_id)
    priced = []
    for row in rows:
        x = dict(row)
        if price_catalog is not None and x.get("price_code"):
            resolved = price_catalog.resolve(str(x["price_code"]), year, x["unit"])
            if resolved["status"] == "ok":
                x["unit_price"] = resolved["unit_price"]
            elif resolved["status"] != "not_found":
                raise ValueError(f"قیمت‌گذاری نامعتبر برای {x['id']}: {resolved['status']}")
        priced.append(x)
    boq = build_boq(priced, aggregate=True)
    estimate = build_estimate(boq, factors=factors or {}, aggregate=False)
    return {
        "project_id": project_id,
        "project_name": project_name,
        "takeoffs": priced,
        "boq": boq,
        "boq_summary": boq_summary(boq),
        "estimate": estimate,
        "integrity": {
            "healthy": True,
            "takeoff_count": len(priced),
            "boq_line_count": len(boq),
            "duplicate_source_ids": 0,
        },
    }

def convert_takeoff_unit(row: dict[str, Any], target_unit: str) -> dict[str, Any]:
    x = dict(row)
    x["quantity"] = convert(float(x["quantity"]), x["unit"], target_unit)
    x["unit"] = normalize_unit(target_unit)
    return x
