"""P41 BIM/IFC 2.0: normalized IFC takeoff and drawing discrepancy controls."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping
from .model import BIMElement

@dataclass(frozen=True)
class BIMQuantity:
    global_id:str; kind:str; quantity_name:str; quantity:float; unit:str
    def __post_init__(self):
        if not self.global_id or self.quantity<0: raise ValueError("invalid BIM quantity")

@dataclass(frozen=True)
class BIMDrawingDiscrepancy:
    key:str; bim_value:float|None; drawing_value:float|None; delta:float|None; status:str
    def __post_init__(self):
        if self.status not in {"match","mismatch","missing_bim","missing_drawing","review"}: raise ValueError("invalid discrepancy status")

def extract_quantities(elements:Iterable[BIMElement])->tuple[BIMQuantity,...]:
    out=[]
    for e in elements:
        for key,value in e.geometry.items():
            if key.casefold() in {"volume","netvolume","grossvolume","area","length"} and value is not None:
                try: out.append(BIMQuantity(e.global_id,e.kind,key.casefold(),float(value),
                                             "m3" if "volume" in key.casefold() else "m2" if "area" in key.casefold() else "m"))
                except (TypeError,ValueError): pass
    return tuple(out)

def compare_bim_to_drawing(bim:Mapping[str,float], drawing:Mapping[str,float], *, tolerance:float=.001):
    keys=tuple(dict.fromkeys((*bim.keys(),*drawing.keys())))
    out=[]
    for key in keys:
        b=bim.get(key); d=drawing.get(key)
        if b is None: status="missing_bim"; delta=None
        elif d is None: status="missing_drawing"; delta=None
        else:
            delta=float(b)-float(d); status="match" if abs(delta)<=tolerance else "mismatch"
        out.append(BIMDrawingDiscrepancy(key,b,d,delta,status))
    return tuple(out)
