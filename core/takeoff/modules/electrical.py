"""Electrical quantity operations."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any

@dataclass(frozen=True)
class ElectricalResult:
    item: str
    quantity: float
    unit: str
    formula: str

def _n(v,name):
    if isinstance(v, bool): raise ValueError(f"{name} must be numeric")
    try: x=float(v)
    except (TypeError,ValueError,OverflowError): raise ValueError(f"{name} must be numeric")
    if not math.isfinite(x): raise ValueError(f"{name} must be finite")
    if x<0: raise ValueError(f"{name} must be >= 0")
    if name == "count" and not x.is_integer():
        raise ValueError("تعداد قطعات باید عدد صحیح باشد")
    return x

def calculate_electrical_item(item: str, **p: Any) -> ElectricalResult:
    k=item.casefold().replace(" ","_")
    if k in {"cable","wire","کابل","سیم"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return ElectricalResult(item,q,"m","L×تعداد")
    if k in {"conduit","لوله_برق"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return ElectricalResult(item,q,"m","L×تعداد")
    if k in {"panel","board","تابلو"}:
        q=_n(p.get("count",1),"count"); return ElectricalResult(item,q,"عدد","تعداد")
    if k in {"light","lighting","روشنایی","چراغ","socket","outlet","پریز"}:
        q=_n(p.get("count",1),"count"); return ElectricalResult(item,q,"عدد","تعداد")
    if k in {"earthing","earth","ارت"}:
        q=_n(p["length"],"length"); return ElectricalResult("ارت",q,"m","L")
    if k in {"cable_tray","سینی_کابل"}:
        q=_n(p["length"],"length"); return ElectricalResult("سینی کابل",q,"m","L")
    raise KeyError(f"unsupported electrical item: {item}")
