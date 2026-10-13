"""Steel quantity domain: members, plates, bolts, welds, assemblies and shop parts."""
from __future__ import annotations
from .models import DomainQuantity, positive, count

def steel_quantities(kind, **p):
    k=str(kind).strip().casefold()
    if k in {"bolt","connection"}:
        q=count(p["quantity"],"quantity")
        return DomainQuantity("steel",k,q,"عدد","تعداد تأییدشده","IR-NBR-10","1401").validate()
    n=count(p["count"])
    if k in {"beam","column","bracing","truss","plate_girder","section","assembly","shop_part"}:
        q=positive(p["length"],"length")*positive(p["unit_weight"],"unit_weight")*n
        return DomainQuantity("steel",k,q,"kg","L×وزن واحد×تعداد","IR-NBR-10","1401").validate()
    if k in {"plate","stiffener"}:
        material_source=p.get("density_source")
        if not isinstance(material_source,str) or not material_source.strip():
            raise ValueError("مرجع چگالی واقعی ورق یا سخت‌کننده الزامی است")
        density=positive(p["density_kg_m3"],"density_kg_m3")
        q=(positive(p["length"],"length")*positive(p["width"],"width")
           *positive(p["thickness"],"thickness")*density*n)
        return DomainQuantity("steel",k,q,"kg",
                              "L×W×t×چگالی مستند×تعداد","IR-NBR-10","1401").validate()
    if k in {"weld"}:
        q=positive(p["length"],"length")*positive(p["weld_unit_weight"],"weld_unit_weight")*n
        return DomainQuantity("steel","weld",q,"kg","L×وزن واحد جوش×تعداد","IR-NBR-10","1401").validate()
    raise KeyError(f"unsupported steel item: {kind}")
