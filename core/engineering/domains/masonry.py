"""Masonry quantity domain: walls, openings, confined components and materials."""
from __future__ import annotations
from .models import DomainQuantity, positive, count

def masonry_quantities(kind, **p):
    k=str(kind).strip().casefold(); n=count(p.get("count",1))
    if k in {"wall","bearing","confined"}:
        q=max(0.0,positive(p["length"],"length")*positive(p["height"],"height")-positive(p.get("openings",0),"openings"))*positive(p["thickness"],"thickness")*n
        return DomainQuantity("masonry",k,q,"m3","(L×H−بازشو)×t×تعداد","IR-NBR-08","1398").validate()
    if k in {"opening","material"}:
        q=count(p.get("quantity",1),"quantity")
        return DomainQuantity("masonry",k,q,"عدد","تعداد","IR-NBR-08","1398").validate()
    raise KeyError(f"unsupported masonry item: {kind}")
