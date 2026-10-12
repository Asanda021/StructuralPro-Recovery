"""Professional BOQ/estimating controls for StructuralPro Phase 4.

Price mapping is explicit and provenance-preserving. Cross-source duplicates are
reported rather than silently deleted or guessed.
"""
from __future__ import annotations

from typing import Any, Iterable
import math

from core.takeoff.boq import build_boq, validate_boq_structure, boq_summary
from core.takeoff.costing import cost_breakdown


def _num(value: Any, name: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return x


def map_prices(rows: Iterable[dict[str, Any]], catalog, *, year: int | None = None,
               strict: bool = False) -> dict[str, Any]:
    mapped = []
    unresolved = []
    for row in rows:
        out = dict(row)
        code = str(out.get("price_code") or out.get("item_code") or "").strip()
        if not code:
            out["price_status"] = "missing_code"
            unresolved.append({"source": out.get("source", ""), "status": "missing_code"})
            mapped.append(out)
            continue
        result = catalog.resolve(code, year, out.get("unit") or None)
        out["price_status"] = result["status"]
        if result["status"] == "ok":
            item = result["item"]
            out["unit_price"] = float(result["unit_price"])
            out["price_code"] = item.code
            out["description"] = out.get("description") or item.description
            out["chapter"] = out.get("chapter") or item.chapter
            out["group"] = out.get("group") or item.group
            out["price_source"] = {
                "year": item.year, "code": item.code, "group": item.group,
                "chapter": item.chapter, "unit": item.unit,
            }
        else:
            unresolved.append({
                "source": out.get("source", ""), "price_code": code,
                "status": result["status"],
            })
            out["needs_price_review"] = True
        mapped.append(out)
    if strict and unresolved:
        raise ValueError(f"unresolved price mappings: {unresolved}")
    return {"rows": mapped, "unresolved": unresolved}


def find_cross_source_duplicates(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect stable object/source overlaps without deleting either record."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    duplicates = []
    for row in rows:
        object_id = str(row.get("object_id") or row.get("global_id") or "").strip()
        if not object_id:
            continue
        source_type = str(row.get("source_type") or "").strip().lower()
        key = (object_id, str(row.get("unit") or "").strip())
        previous = seen.get(key)
        if previous and str(previous.get("source_type") or "").strip().lower() != source_type:
            duplicates.append({
                "object_id": object_id,
                "unit": key[1],
                "first_source": previous.get("source", ""),
                "first_source_type": previous.get("source_type", ""),
                "duplicate_source": row.get("source", ""),
                "duplicate_source_type": row.get("source_type", ""),
                "status": "needs_confirmation",
            })
        else:
            seen[key] = row
    return duplicates


def prepare_estimate_rows(rows: Iterable[dict[str, Any]], *, default_waste_percent: float = 0.0,
                          default_allowance_quantity: float = 0.0) -> list[dict[str, Any]]:
    waste = _num(default_waste_percent, "default_waste_percent")
    allowance = _num(default_allowance_quantity, "default_allowance_quantity")
    out = []
    for row in rows:
        r = dict(row)
        r["waste_percent"] = _num(r.get("waste_percent", waste), "waste_percent")
        r["allowance_quantity"] = _num(r.get("allowance_quantity", allowance), "allowance_quantity")
        out.append(r)
    return out


def build_professional_estimate(rows: Iterable[dict[str, Any]], *, catalog=None,
                                year: int | None = None, factors=None,
                                aggregate: bool = True, strict_prices: bool = False,
                                strict_duplicates: bool = True,
                                default_waste_percent: float = 0.0,
                                default_allowance_quantity: float = 0.0) -> dict[str, Any]:
    prepared = prepare_estimate_rows(
        rows,
        default_waste_percent=default_waste_percent,
        default_allowance_quantity=default_allowance_quantity,
    )
    price_result = {"rows": prepared, "unresolved": []}
    if catalog is not None:
        price_result = map_prices(prepared, catalog, year=year, strict=strict_prices)
        prepared = price_result["rows"]

    duplicates = find_cross_source_duplicates(prepared)
    if strict_duplicates and duplicates:
        raise ValueError(f"cross-source duplicate review required: {duplicates}")

    boq = build_boq(prepared, aggregate=aggregate)
    validation = validate_boq_structure(boq)
    if not validation["valid"]:
        raise ValueError(f"invalid BOQ: {validation['errors']}")
    factors = {str(k): _num(v, "factor rate") for k, v in (factors or {}).items()}
    cost = cost_breakdown(boq, factors)
    return {
        "boq": boq,
        "summary": boq_summary(boq),
        "validation": validation,
        "cost": cost,
        "price_mapping": price_result,
        "duplicate_review": duplicates,
        "finalizable": not price_result["unresolved"] and not duplicates,
        "factors": factors,
    }
