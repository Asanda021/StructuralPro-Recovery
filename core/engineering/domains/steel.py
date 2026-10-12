"""Steel quantity domain: members, plates, bolts, welds, assemblies and shop parts."""
from __future__ import annotations
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
        q=positive(p["length"],"length")*positive(p.get("weld_unit_weight",1.0),"weld_unit_weight")*n
        return DomainQuantity("steel","weld",q,"kg","L×وزن واحد جوش×تعداد","IR-NBR-10","1401").validate()
    raise KeyError(f"unsupported steel item: {kind}")
