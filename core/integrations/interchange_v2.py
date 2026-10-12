"""P117 — validated interchange boundary for BOQ/estimate rows.
Rejects malformed rows instead of silently coercing bad project evidence.
"""
from __future__ import annotations
from typing import Any, Iterable

REQUIRED=("price_code","description","quantity","unit")

def validate_import_rows(rows: Iterable[dict[str,Any]], *, strict=True) -> list[dict[str,Any]]:
    out=[]
    for i, raw in enumerate(rows,1):
        if not isinstance(raw,dict):
            raise ValueError(f"row {i}: expected object")
        missing=[k for k in REQUIRED if str(raw.get(k,"")).strip()==""]
        if missing: raise ValueError(f"row {i}: missing required fields: {missing}")
        try: q=float(raw["quantity"])
        except (TypeError,ValueError): raise ValueError(f"row {i}: quantity is not numeric")
        if q<0 or q!=q or q in (float("inf"),float("-inf")): raise ValueError(f"row {i}: invalid quantity")
        r=dict(raw); r["price_code"]=str(r["price_code"]).strip(); r["description"]=str(r["description"]).strip()
        r["unit"]=str(r["unit"]).strip(); r["quantity"]=q
        if "unit_price" in r and r["unit_price"] not in (None,""):
            try: r["unit_price"]=float(r["unit_price"])
            except (TypeError,ValueError): raise ValueError(f"row {i}: invalid unit_price")
            if r["unit_price"]<0: raise ValueError(f"row {i}: invalid unit_price")
        out.append(r)
    if strict and not out: raise ValueError("import contains no data rows")
    return out

def import_summary(rows: Iterable[dict[str,Any]]) -> dict[str,Any]:
    rows=list(rows)
    return {"row_count":len(rows),"quantity_total":sum(float(r["quantity"]) for r in rows),
            "codes":sorted({str(r["price_code"]) for r in rows})}
