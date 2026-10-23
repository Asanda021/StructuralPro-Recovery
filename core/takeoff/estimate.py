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
    from collections import Counter
    import json
    def base_key(row, index):
        return str(row.get("price_code") or row.get("item_code") or row.get("description") or row.get("source") or index)
    counts = [Counter(base_key(r,i) for i,r in enumerate(snapshot.get("boq",[]) or [])) for snapshot in (old,new)]
    duplicate_codes = {key for count in counts for key,n in count.items() if n > 1}
    def index_rows(snapshot):
        result = {}
        for i,row in enumerate(snapshot.get("boq",[]) or []):
            key = base_key(row,i)
            if key in duplicate_codes:
                sources = row.get("source_ids") or [row.get("source_id") or row.get("source")]
                if not all(isinstance(x,str) and x.strip() for x in sources):
                    raise ValueError("مقایسه ردیف‌های همنام به هویت منبع نیاز دارد")
                key += ":" + json.dumps([sorted(sources),row.get("item_code"),row.get("unit"),row.get("group")],ensure_ascii=False)
            if key in result:
                raise ValueError("هویت ردیف مقایسه تکراری است")
            result[key] = row
        return result
    old_rows, new_rows = index_rows(old), index_rows(new)
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
