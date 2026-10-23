"""Professional estimate orchestration with explicit finalization gates."""
from __future__ import annotations
from typing import Iterable,Any
from core.takeoff.boq import build_boq,validate_boq_structure,boq_summary
from core.takeoff.costing import cost_breakdown
from core.commercial.exact_values import number,wire,exact,display_percent
def _num(value,name):return wire(number(value,name))
def _validate_factors(factors):
    out={}
    for name,value in (factors or {}).items():
        key=str(name).strip()
        if not key: raise ValueError("factor name cannot be empty")
        out[key]=_num(value,"factor rate")
    return out
def build_estimate(rows:Iterable[Any],*,factors=None,aggregate=True)->dict[str,Any]:
    normalized=_validate_factors(factors); boq=build_boq(rows,aggregate=aggregate); validation=validate_boq_structure(boq)
    cost=cost_breakdown(boq,normalized)
    return {"boq":boq,"summary":boq_summary(boq),"validation":validation,"cost":cost,"factors":normalized,"finalizable":bool(validation["valid"] and all(r.get("unit_price") is not None for r in boq if r.get("status") != "cancelled"))}

@exact
def compare_estimates(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compare two estimate snapshots without mutating either input."""
    a = number(old.get("cost", {}).get("grand_total", 0), "جمع قبلی")
    b = number(new.get("cost", {}).get("grand_total", 0), "جمع جدید")
    old_rows = {str(r.get("price_code") or r.get("item_code") or r.get("description") or r.get("source") or i): r
                for i, r in enumerate(old.get("boq", []) or [])}
    new_rows = {str(r.get("price_code") or r.get("item_code") or r.get("description") or r.get("source") or i): r
                for i, r in enumerate(new.get("boq", []) or [])}
    keys = old_rows.keys() | new_rows.keys()
    line_changes = []
    for key in sorted(keys):
        before, after = old_rows.get(key), new_rows.get(key)
        bq = number((before or {}).get("quantity", 0) or 0, "quantity")
        aq = number((after or {}).get("quantity", 0) or 0, "quantity")
        bp = number((before or {}).get("unit_price", 0) or 0, "unit_price")
        ap = number((after or {}).get("unit_price", 0) or 0, "unit_price")
        if bq != aq or bp != ap:
            line_changes.append({
                "key": key, "old_quantity": bq, "new_quantity": aq, "quantity_delta": aq - bq,
                "old_unit_price": bp, "new_unit_price": ap, "unit_price_delta": ap - bp,
            })
    return wire({
        "old_total": a, "new_total": b, "delta": b - a,
        "delta_percent": display_percent(b - a, a),
        "line_changes": line_changes,
        "added_lines": [k for k in new_rows.keys() - old_rows.keys()],
        "removed_lines": [k for k in old_rows.keys() - new_rows.keys()],
    })
