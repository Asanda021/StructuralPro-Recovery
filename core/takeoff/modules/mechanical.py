"""Mechanical MEP quantity operations."""
from __future__ import annotations
from dataclasses import dataclass
import math
from decimal import Decimal, InvalidOperation
from typing import Any

@dataclass(frozen=True)
class MechanicalResult:
    item: str
    quantity: float
    unit: str
    formula: str

def _checked(item: str, quantity: float, unit: str, formula: str) -> MechanicalResult:
    """Reject arithmetic overflow before returning any physical quantity."""
    if not math.isfinite(quantity):
        raise ValueError("derived quantity must be finite")
    return MechanicalResult(item, quantity, unit, formula)

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

def calculate_mechanical_item(item: str, **p: Any) -> MechanicalResult:
    k=item.casefold().replace(" ","_")
    if k in {"pipe","pipe_length","لوله"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return _checked("لوله",q,"m","L×تعداد")
    if k in {"duct","duct_length","کانال"}:
        q=_n(p["length"],"length")*_n(p.get("count",1),"count"); return _checked("کانال",q,"m","L×تعداد")
    if k in {"duct_area","کانال_سطح"}:
        q=2*(_n(p["width"],"width")+_n(p["height"],"height"))*_n(p["length"],"length"); return _checked("سطح کانال",q,"m2","2×(W+H)×L")
    if k in {"insulation","pipe_insulation","عایق_لوله"}:
        q=3.141592653589793*_n(p["diameter"],"diameter")*_n(p["length"],"length"); return _checked("عایق لوله",q,"m2","π×D×L")
    if k in {"equipment","equipment_count","تجهیز"}:
        q=_n(p.get("count",1),"count"); return _checked("تجهیزات",q,"عدد","تعداد")
    if k in {"valve","fixture","شیر","اتصال"}:
        q=_n(p.get("count",1),"count"); return _checked(item,q,"عدد","تعداد")
    raise KeyError(f"unsupported mechanical item: {item}")
