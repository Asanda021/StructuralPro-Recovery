"""Professional estimate orchestration with explicit finalization gates."""
from __future__ import annotations
from typing import Iterable,Any
import math
from core.takeoff.boq import build_boq,validate_boq_structure,boq_summary
from core.takeoff.costing import cost_breakdown
def _num(value,name):
    x=float(value)
    if not math.isfinite(x) or x<0: raise ValueError(f"{name} must be finite and non-negative")
    return x
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
    return {"boq":boq,"summary":boq_summary(boq),"validation":validation,"cost":cost,"factors":normalized,"finalizable":bool(validation["valid"])}

def compare_estimates(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Compare two estimate snapshots without mutating either input."""
    a = float(old.get("cost", {}).get("grand_total", 0) or 0)
    b = float(new.get("cost", {}).get("grand_total", 0) or 0)
    if not all(math.isfinite(x) for x in (a, b)) or a < 0 or b < 0:
        raise ValueError("estimate totals must be finite and non-negative")
    old_rows = {str(r.get("price_code") or r.get("item_code") or r.get("description") or r.get("source") or i): r
                for i, r in enumerate(old.get("boq", []) or [])}
    new_rows = {str(r.get("price_code") or r.get("item_code") or r.get("description") or r.get("source") or i): r
                for i, r in enumerate(new.get("boq", []) or [])}
    keys = old_rows.keys() | new_rows.keys()
    line_changes = []
    for key in sorted(keys):
        before, after = old_rows.get(key), new_rows.get(key)
        bq = float((before or {}).get("quantity", 0) or 0)
        aq = float((after or {}).get("quantity", 0) or 0)
        bp = float((before or {}).get("unit_price", 0) or 0)
        ap = float((after or {}).get("unit_price", 0) or 0)
        if bq != aq or bp != ap:
            line_changes.append({
                "key": key, "old_quantity": bq, "new_quantity": aq, "quantity_delta": aq - bq,
                "old_unit_price": bp, "new_unit_price": ap, "unit_price_delta": ap - bp,
            })
    return {
        "old_total": a, "new_total": b, "delta": b - a,
        "delta_percent": 0.0 if a == 0 else (b - a) / a * 100,
        "line_changes": line_changes,
        "added_lines": [k for k in new_rows.keys() - old_rows.keys()],
        "removed_lines": [k for k in old_rows.keys() - new_rows.keys()],
    }
