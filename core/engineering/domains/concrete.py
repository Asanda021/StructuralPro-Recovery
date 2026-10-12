"""Concrete quantity domain: members, reinforcement, embeds and roofs/stairs."""
from __future__ import annotations
from .models import DomainQuantity, positive, count

def concrete_quantities(kind, **p):
    k=str(kind).strip().casefold()
    n=count(p.get("count",1))
    if k in {"beam","column","slab","wall","roof"}:
        q=positive(p["length"],"length")*positive(p["width"],"width")*positive(p["depth"],"depth")*n
        return DomainQuantity("concrete",k,q,"m3","L×W×D×تعداد","IR-NBR-09","1399").validate()
    if k in {"frame","stairs"}:
        q=positive(p["concrete_volume"],"concrete_volume")*n
        return DomainQuantity("concrete",k,q,"m3","حجم ورودی×تعداد","IR-NBR-09","1399").validate()
    if k in {"reinforcement","rebar","stirrup","tie"}:
        q=positive(p["length"],"length")*positive(p["unit_weight"],"unit_weight")*n
        return DomainQuantity("concrete","reinforcement",q,"kg","L×وزن واحد×تعداد","IR-NBR-09","1399").validate()
    if k in {"embed","embedded_item"}:
        q=count(p.get("quantity",1),"quantity")
        return DomainQuantity("concrete","embedded_item",q,"عدد","تعداد","IR-NBR-09","1399").validate()
    raise KeyError(f"unsupported concrete item: {kind}")
