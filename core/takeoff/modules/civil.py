"""Civil, site and road quantity operations."""
from __future__ import annotations
from dataclasses import dataclass
import math
from decimal import Decimal, InvalidOperation
from typing import Any

@dataclass(frozen=True)
class CivilResult:
    item: str
    quantity: float
    unit: str
    formula: str

    def __post_init__(self):
        if not math.isfinite(self.quantity) or self.quantity < 0:
            raise ValueError("derived quantity must be finite and nonnegative")

def _mul(*factors):
    result = 1.0
    for factor in factors:
        result *= factor
    if not math.isfinite(result):
        raise ValueError("derived quantity must be finite")
    if result == 0.0 and all(factor > 0.0 for factor in factors):
        raise ValueError("derived quantity underflow: nonzero product rounded to zero")
    return result

def _n(v,name):
    if isinstance(v, bool): raise ValueError(f"{name} must be numeric")
    try: x=float(v)
    except (TypeError,ValueError,OverflowError): raise ValueError(f"{name} must be numeric")
    if not math.isfinite(x): raise ValueError(f"{name} must be finite")
    if x == 0.0:
        try:
            lost_nonzero = Decimal(str(v)) != 0
        except InvalidOperation:
            lost_nonzero = False
        if lost_nonzero:
            raise ValueError(f"{name} underflow: nonzero input rounded to zero")
    if name == "count":
        try:
            is_exact_count = x.is_integer() and Decimal(str(v)) == Decimal(int(x))
        except (InvalidOperation, ValueError, OverflowError):
            is_exact_count = False
        if not is_exact_count:
            raise ValueError("count must be an exactly representable integer")
    if x<0: raise ValueError(f"{name} must be >= 0")
    return x

def calculate_civil_item(item: str, **p: Any) -> CivilResult:
    k=item.casefold().replace(" ","_")
    if k in {"excavation","خاکبرداری","خاک_برداری"}:
        q=_mul(_n(p["length"],"length"),_n(p["width"],"width"),_n(p["depth"],"depth")); return CivilResult("خاکبرداری",q,"m3","L×W×D")
    if k in {"backfill","خاکریزی","خاک_ریزی"}:
        excavation=_n(p["excavation"],"excavation")
        deductions=_n(p.get("deductions",0),"deductions")
        if deductions > excavation:
            raise ValueError("backfill deductions cannot exceed excavation volume")
        q=excavation-deductions
        return CivilResult("خاکریزی",q,"m3","خاکبرداری−کسرها")
    if k in {"paving","concrete_yard","بتن_محوطه"}:
        q=_mul(_n(p["length"],"length"),_n(p["width"],"width"),_n(p["thickness"],"thickness")); return CivilResult("بتن محوطه",q,"m3","L×W×t")
    if k in {"asphalt","آسفالت"}:
        q=_mul(_n(p["length"],"length"),_n(p["width"],"width"),_n(p["thickness"],"thickness")); return CivilResult("آسفالت",q,"m3","L×W×t")
    if k in {"curb","جدول"}:
        q=_mul(_n(p["length"],"length"),_n(p.get("count",1),"count")); return CivilResult("جدول",q,"m","L×تعداد")
    if k in {"drainage","زهکشی"}:
        q=_n(p["length"],"length"); return CivilResult("زهکشی",q,"m","L")
    if k in {"fence_wall","wall","دیوارکشی"}:
        q=_mul(_n(p["length"],"length"),_n(p["height"],"height")); return CivilResult("دیوارکشی",q,"m2","L×H")
    raise KeyError(f"unsupported civil item: {item}")
