"""Unified drawing -> canonical takeoff -> BOQ pipeline with integrity gates."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
import math
from core.takeoff.units import normalize_unit

@dataclass(frozen=True)
class PipelineRow:
    source: str
    description: str
    quantity: float
    unit: str
    price_code: str | None = None
    unit_price: float | None = None
    total: float | None = None

class DrawingTakeoffPipeline:
    def __init__(self, price_resolver=None):
        self.price_resolver = price_resolver

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[PipelineRow]:
        out=[]; seen=set()
        for i,r in enumerate(rows,1):
            source=str(r.get("source") or "").strip()
            if not source: source=f"drawing:{i}"
            if source in seen:
                raise ValueError(f"منبع متره تکراری و مستعد دوباره‌شماری: {source}")
            seen.add(source)
            q=float(r.get("quantity",0))
            if not math.isfinite(q) or q < 0: raise ValueError("quantity must be finite and non-negative")
            unit=normalize_unit(r.get("unit",""))
            code=r.get("price_code")
            price=None
            if code and self.price_resolver:
                resolved=self.price_resolver(code)
                if resolved is None: raise ValueError(f"قیمت پیدا نشد: {code}")
                price=float(resolved)
            elif r.get("unit_price") is not None:
                price=float(r["unit_price"])
            if price is not None and (not math.isfinite(price) or price < 0):
                raise ValueError("unit_price must be finite and non-negative")
            total=None if price is None else q*price
            out.append(PipelineRow(source,str(r.get("description","")),q,unit,code,price,total))
        return out

    def aggregate(self, rows: Iterable[PipelineRow]) -> list[PipelineRow]:
        groups={}
        for r in rows:
            key=(r.price_code or r.description,r.unit,r.unit_price)
            old=groups.get(key)
            if old is None: groups[key]=r
            else:
                q=old.quantity+r.quantity
                total=None if old.unit_price is None else q*old.unit_price
                groups[key]=PipelineRow(old.source,old.description,q,old.unit,old.price_code,old.unit_price,total)
        return list(groups.values())

    def to_boq(self, rows: Iterable[PipelineRow]) -> list[dict[str,Any]]:
        return [{"source":r.source,"description":r.description,"quantity":r.quantity,"unit":r.unit,
                 "price_code":r.price_code,"unit_price":r.unit_price,"total":r.total} for r in rows]
