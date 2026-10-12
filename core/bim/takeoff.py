"""BIM-to-quantity bridge. Only explicit IFC quantities are converted."""
from __future__ import annotations
from dataclasses import dataclass
from .model import BIMElement
@dataclass(frozen=True)
class BIMQuantity:
    global_id:str; item_code:str; description:str; quantity:float; unit:str; source_id:str
def quantities(elements):
    out=[]
    for e in elements:
        g=e.geometry
        if "volume" in g:
            out.append(BIMQuantity(e.global_id,f"BIM-{e.kind.upper()}-VOL",e.name or e.kind,g["volume"],"m3",e.source_id))
        elif "netvolume" in g:
            out.append(BIMQuantity(e.global_id,f"BIM-{e.kind.upper()}-NETVOL",e.name or e.kind,g["netvolume"],"m3",e.source_id))
        elif "area" in g:
            out.append(BIMQuantity(e.global_id,f"BIM-{e.kind.upper()}-AREA",e.name or e.kind,g["area"],"m2",e.source_id))
    return tuple(out)
