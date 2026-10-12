"""Deterministic BOQ costing with auditable factor application."""
from __future__ import annotations
from typing import Iterable, Any
import math
def _finite_nonnegative(value, field):
    number=float(value)
    if not math.isfinite(number) or number<0: raise ValueError(f"{field} must be finite and non-negative")
    return number
def cost_breakdown(rows:Iterable[Any], factors:dict[str,float]|None=None)->dict[str,Any]:
    factors=factors or {}; base=0.0; by_group={}; by_code={}
    for r in rows:
        d=r if isinstance(r,dict) else vars(r)
        if str(d.get("status") or "active").strip().lower()=="cancelled": continue
        quantity=_finite_nonnegative(d.get("effective_quantity",d.get("quantity",0)) or 0,"quantity")
        unit_price=_finite_nonnegative(d.get("unit_price",0) or 0,"unit_price")
        raw_total=d.get("total"); amount=_finite_nonnegative(raw_total if raw_total is not None else quantity*unit_price,"total")
        group=str(d.get("group") or d.get("category") or "سایر"); code=str(d.get("price_code") or d.get("item_code") or "بدون کد")
        base+=amount
        if not math.isfinite(base): raise ValueError("cost total overflow")
        by_group[group]=by_group.get(group,0)+amount; by_code[code]=by_code.get(code,0)+amount
    applied={}; sequence=[]; subtotal=base
    for name,rate in factors.items():
        key=str(name).strip()
        if not key: raise ValueError("factor name cannot be empty")
        rate=_finite_nonnegative(rate,"factor rate"); delta=subtotal*rate
        if not math.isfinite(delta): raise ValueError("factor result overflow")
        applied[key]=delta; sequence.append({"name":key,"base":subtotal,"rate":rate,"delta":delta,"subtotal":subtotal+delta})
        subtotal+=delta
        if not math.isfinite(subtotal): raise ValueError("grand total overflow")
    return {"base":base,"factors":applied,"factor_sequence":sequence,"grand_total":subtotal,"by_group":by_group,"by_code":by_code}
