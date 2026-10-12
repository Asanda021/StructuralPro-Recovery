"""Steel quantity domain: members, plates, bolts, welds, assemblies and shop parts."""
from __future__ import annotations
import math
from .models import DomainQuantity, positive, count

def steel_quantities(kind, **p):
    k=str(kind).strip().casefold()
    n=count(p.get("count",1))
    if k in {"beam","column","bracing","truss","plate_girder","section","assembly","shop_part"}:
        q=positive(p["length"],"length")*positive(p["unit_weight"],"unit_weight")*n
        return DomainQuantity("steel",k,q,"kg","L×وزن واحد×تعداد","IR-NBR-10","1401").validate()
    if k in {"plate","stiffener"}:
        q=positive(p["length"],"length")*positive(p["width"],"width")*positive(p["thickness"],"thickness")*7_850*n
        return DomainQuantity("steel",k,q,"kg","L×W×t×7850×تعداد","IR-NBR-10","1401").validate()
    if k in {"bolt","connection"}:
        q=count(p.get("quantity",1),"quantity")
        return DomainQuantity("steel",k,q,"عدد","تعداد","IR-NBR-10","1401").validate()
    if k in {"weld"}:
        # Weld mass is not determined by length alone. The previous 1 kg/m
        # default silently invented a payable engineering quantity.
        if "weld_unit_weight" not in p:
            raise ValueError("وزن واحد جوش باید صریح و مستند وارد شود (weld_unit_weight)")
        if p.get("weld_unit_weight_unit") != "kg/m":
            raise ValueError("واحد وزن واحد جوش باید صریحاً kg/m باشد")
        ref = p.get("weld_detail_ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("مرجع دیتایل یا مشخصات تأییدشده جوش الزامی است")
        if isinstance(p.get("length"), bool) or isinstance(p["weld_unit_weight"], bool):
            raise ValueError("طول و وزن واحد جوش باید عدد مهندسی معتبر باشند")
        length = positive(p["length"], "length")
        unit_weight = positive(p["weld_unit_weight"], "weld_unit_weight")
        if not (math.isfinite(length) and math.isfinite(unit_weight) and unit_weight > 0):
            raise ValueError("طول و وزن واحد جوش باید متناهی و وزن واحد بزرگ‌تر از صفر باشد")
        if n < 1:
            raise ValueError("تعداد جوش باید عدد صحیح مثبت باشد")
        q = length * unit_weight * n
        if not math.isfinite(q):
            raise ValueError("وزن محاسبه‌شده جوش نامعتبر است")
        return DomainQuantity("steel", "weld", q, "kg",
                              f"L×وزن واحد صریح (kg/m)×تعداد؛ مرجع دیتایل: {ref.strip()}",
                              "IR-NBR-10", "1401").validate()
    raise KeyError(f"unsupported steel item: {kind}")
