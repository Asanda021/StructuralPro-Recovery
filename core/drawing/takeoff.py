"""Convert classified drawing elements into quantity candidates.

Only explicit drawing geometry is used. Missing engineering dimensions remain
warnings instead of being silently guessed.
"""
from __future__ import annotations
from .models import EngineeringElement

def drawing_takeoff(elements) -> tuple[dict, ...]:
    rows=[]
    for element in elements:
        if not isinstance(element,EngineeringElement): raise TypeError("elements must contain EngineeringElement")
        g=element.geometry
        row={
            "element_id":element.element_id,
            "domain":element.domain,
            "kind":element.kind,
            "confidence":element.confidence,
            "quantity":None,
            "unit":"",
            "formula":"",
            "warnings":[],
            "source_ids":element.source_ids,
        }
        if element.kind in {"beam","column","member"} and g.get("length",0) > 0:
            row.update(quantity=g["length"],unit="m",formula="drawing length")
        elif element.kind in {"slab","wall"} and g.get("width",0) > 0 and g.get("height",0) > 0:
            row.update(quantity=g["width"]*g["height"],unit="m2",formula="drawing width×height")
        elif element.kind == "isolated" and all(g.get(k,0)>0 for k in ("width","height")):
            row.update(quantity=g["width"]*g["height"],unit="m2",formula="drawing width×height")
        else:
            row["warnings"].append("ابعاد کافی برای متره خودکار در نقشه موجود نیست")
        rows.append(row)
    return tuple(rows)
