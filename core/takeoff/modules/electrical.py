"""Electrical quantity operations."""
from __future__ import annotations
from dataclasses import dataclass
import math
from decimal import Decimal, InvalidOperation
from typing import Any

@dataclass(frozen=True)
class ElectricalResult:
    item: str
    quantity: float
    unit: str
    formula: str

def _checked(item: str, quantity: float, unit: str, formula: str) -> ElectricalResult:
    """Reject arithmetic overflow before returning any physical quantity."""
    if not math.isfinite(quantity):
        raise ValueError("derived quantity must be finite")
    return ElectricalResult(item, quantity, unit, formula)

def _n(v,name):
    if isinstance(v, bool): raise ValueError(f"{name} must be numeric")
    try: x=float(v)
    except (TypeError,ValueError,OverflowError): raise ValueError(f"{name} must be numeric")
    if not math.isfinite(x): raise ValueError(f"{name} must be finite")
    # A positive/negative nonzero explicit input must not silently become zero
    # when its magnitude is below binary64 resolution. Literal zero remains
    # subject to the pre-existing zero policy.
    if x == 0.0:
        try:
            lost_nonzero = Decimal(str(v)) != 0
        except InvalidOperation:
            lost_nonzero = False
        if lost_nonzero:
            raise ValueError(f"{name} underflow: nonzero input rounded to zero")
    if x<0: raise ValueError(f"{name} must be >= 0")
    if name == "count" and not x.is_integer():
        raise ValueError("تعداد قطعات باید عدد صحیح باشد")
    if not isinstance(v, float) and Decimal(str(v)) != Decimal(str(x)):
        raise ValueError(f"{name}: دقت ورودی مستند در تبدیل به float قابل حفظ نیست")
    return x

def calculate_electrical_item(item: str, **p: Any) -> ElectricalResult:
    k=item.casefold().replace(" ","_")
    if k in {"cable","wire","کابل","سیم"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return _checked(item,q,"m","L×تعداد")
    if k in {"conduit","لوله_برق"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return _checked(item,q,"m","L×تعداد")
    if k in {"panel","board","تابلو"}:
        q=_n(p.get("count",1),"count"); return _checked(item,q,"عدد","تعداد")
    if k in {"light","lighting","روشنایی","چراغ","socket","outlet","پریز"}:
        q=_n(p.get("count",1),"count"); return _checked(item,q,"عدد","تعداد")
    if k in {"earthing","earth","ارت"}:
        q=_n(p["length"],"length"); return _checked("ارت",q,"m","L")
    if k in {"cable_tray","سینی_کابل"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return _checked("سینی کابل",q,"m","L×تعداد")
    raise KeyError(f"unsupported electrical item: {item}")
