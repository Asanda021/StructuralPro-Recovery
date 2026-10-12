"""Foundation quantity domain: common shallow/deep foundations and grade beams."""
from __future__ import annotations
from .models import DomainQuantity, positive, count

def foundation_quantities(kind, **p):
    k=str(kind).strip().casefold(); n=count(p.get("count",1))
    if k in {"isolated","strip","combined","strap","mat","pile_cap","grade_beam","foundation_wall"}:
        q=positive(p["length"],"length")*positive(p["width"],"width")*positive(p["depth"],"depth")*n
        return DomainQuantity("foundations",k,q,"m3","L×W×D×تعداد","IR-NBR-07","1400").validate()
    if k in {"pile"}:
        q=positive(p["length"],"length")*3.141592653589793*(positive(p["diameter"],"diameter")/2)**2*n
        return DomainQuantity("foundations","pile",q,"m3","L×π×(D/2)^2×تعداد","IR-NBR-07","1400").validate()
    if k in {"pile_group"}:
        q=positive(p["pile_count"],"pile_count")*positive(p["pile_volume"],"pile_volume")
        return DomainQuantity("foundations","pile_group",q,"m3","تعداد شمع×حجم هر شمع","IR-NBR-07","1400").validate()
    if k in {"foundation_connection"}:
        q=count(p.get("quantity",1),"quantity")
        return DomainQuantity("foundations","foundation_connection",q,"عدد","تعداد","IR-NBR-07","1400").validate()
    raise KeyError(f"unsupported foundation item: {kind}")
