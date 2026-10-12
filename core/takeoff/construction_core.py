"""Production construction quantity core with explicit, auditable quantity rules."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import math
from .element_model import ConstructionElement
from .units import convert, normalize_unit

@dataclass(frozen=True)
class QuantityLine:
    element_id: str
    domain: str
    item_code: str
    description: str
    quantity: float
    unit: str
    formula: str
    source_id: str = "manual"
    waste_rate: float = 0.0
    gross_quantity: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        q=float(self.quantity); w=float(self.waste_rate)
        if not math.isfinite(q) or q < 0: raise ValueError("quantity must be finite and non-negative")
        if not math.isfinite(w) or w < 0 or w > 1: raise ValueError("waste_rate must be between 0 and 1")
        object.__setattr__(self,"quantity",q); object.__setattr__(self,"waste_rate",w)
        object.__setattr__(self,"unit",normalize_unit(self.unit))
        if self.gross_quantity is None:
            object.__setattr__(self,"gross_quantity",q*(1.0+w))
        else:
            g=float(self.gross_quantity)
            if not math.isfinite(g) or g < q: raise ValueError("gross_quantity must be finite and >= net quantity")
            object.__setattr__(self,"gross_quantity",g)

    def as_dict(self):
        return {"element_id":self.element_id,"domain":self.domain,"item_code":self.item_code,
                "description":self.description,"quantity":self.quantity,"unit":self.unit,
                "formula":self.formula,"source_id":self.source_id,"waste_rate":self.waste_rate,
                "gross_quantity":self.gross_quantity,"metadata":dict(self.metadata)}

class ConstructionQuantityCore:
    DOMAINS=("concrete","reinforcement","steel","masonry","finishes","roofing","insulation",
             "doors_windows","plumbing","mechanical","electrical","civil")

    @staticmethod
    def _n(value,name):
        x=float(value)
        if not math.isfinite(x) or x < 0: raise ValueError(f"{name} must be finite and non-negative")
        return x

    @classmethod
    def line(cls,element_id,domain,item_code,description,quantity,unit,formula,*,
             source_id="manual",waste_rate=0.0,metadata=None):
        if domain not in cls.DOMAINS: raise ValueError(f"unsupported construction domain: {domain}")
        return QuantityLine(element_id,domain,item_code,description,quantity,unit,formula,
                            source_id,waste_rate,metadata=metadata or {})

    @classmethod
    def rectangular_volume(cls,element:ConstructionElement,*,item_code="CONCRETE",
                           description="Concrete volume",waste_rate=0.0):
        for name in ("length_m","width_m","height_m"):
            if getattr(element,name) is None: raise ValueError(f"{name} is required for volume")
        q=element.length_m*element.width_m*element.height_m*element.quantity_count
        return cls.line(element.id,"concrete",item_code,description,q,"m3","L×W×H×N",
                        source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def slab_volume(cls,element:ConstructionElement,*,waste_rate=0.0):
        if element.area_m2 is None or element.thickness_m is None: raise ValueError("area_m2 and thickness_m are required for slab volume")
        q=element.area_m2*element.thickness_m*element.quantity_count
        return cls.line(element.id,"concrete","SLAB-CON","Concrete slab",q,"m3","A×t×N",
                        source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def wall_masonry(cls,element:ConstructionElement,*,openings_m2=0.0,waste_rate=0.0):
        if element.area_m2 is not None: gross=element.area_m2
        elif element.length_m is not None and element.height_m is not None: gross=element.length_m*element.height_m*element.quantity_count
        else: raise ValueError("area_m2 or length_m+height_m is required")
        openings=cls._n(openings_m2,"openings_m2")
        if openings > gross: raise ValueError("openings_m2 cannot exceed gross wall area")
        return cls.line(element.id,"masonry","WALL-AREA","Net masonry area",gross-openings,"m2",
                        "gross area−openings",source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def finish_area(cls,element:ConstructionElement,item_code,description,*,openings_m2=0.0,waste_rate=0.0):
        # Compute the net area once; apply waste exactly once at the returned line.
        if element.area_m2 is not None: net=element.area_m2
        elif element.length_m is not None and element.height_m is not None: net=element.length_m*element.height_m*element.quantity_count
        else: raise ValueError("area_m2 or length_m+height_m is required")
        openings=cls._n(openings_m2,"openings_m2")
        if openings > net: raise ValueError("openings_m2 cannot exceed gross finish area")
        return cls.line(element.id,"finishes",item_code,description,net-openings,"m2",
                        "gross area−openings",source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def linear_material(cls,element:ConstructionElement,domain,item_code,description,*,waste_rate=0.0):
        if element.length_m is None: raise ValueError("length_m is required")
        return cls.line(element.id,domain,item_code,description,element.length_m*element.quantity_count,"m","L×N",
                        source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def counted_item(cls,element:ConstructionElement,domain,item_code,description,*,waste_rate=0.0):
        return cls.line(element.id,domain,item_code,description,element.quantity_count,"عدد","N",
                        source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def area_material(cls,element:ConstructionElement,domain,item_code,description,*,waste_rate=0.0):
        if element.area_m2 is None: raise ValueError("area_m2 is required")
        return cls.line(element.id,domain,item_code,description,element.area_m2*element.quantity_count,"m2","A×N",
                        source_id=element.source_id,waste_rate=waste_rate)

    @classmethod
    def rebar_weight(cls,element_id,length_m,diameter_mm,count=1,*,source_id="manual",waste_rate=0.0):
        length=cls._n(length_m,"length_m"); diameter=cls._n(diameter_mm,"diameter_mm"); n=cls._n(count,"count")
        if diameter <= 0: raise ValueError("diameter_mm must be greater than zero")
        unit_weight=diameter**2/162.0
        return cls.line(element_id,"reinforcement","REBAR-WEIGHT","Reinforcement weight",
                        length*unit_weight*n,"kg","L×N×d²/162",source_id=source_id,waste_rate=waste_rate,
                        metadata={"diameter_mm":diameter,"unit_weight_kg_m":unit_weight})

    @classmethod
    def steel_weight(cls,element_id,length_m,unit_weight_kg_m,count=1,*,source_id="manual",waste_rate=0.0):
        q=cls._n(length_m,"length_m")*cls._n(unit_weight_kg_m,"unit_weight_kg_m")*cls._n(count,"count")
        return cls.line(element_id,"steel","STEEL-WEIGHT","Steel weight",q,"kg",
                        "L×N×unit weight",source_id=source_id,waste_rate=waste_rate)

    @classmethod
    def aggregate(cls,lines:Iterable[QuantityLine],*,gross=False):
        result={}
        for line in lines:
            key=(line.domain,line.item_code,line.unit)
            value=line.gross_quantity if gross else line.quantity
            result[key]=result.get(key,0.0)+value
        return result

    @staticmethod
    def convert_line(line:QuantityLine,target_unit:str):
        target=normalize_unit(target_unit)
        q=convert(line.quantity,line.unit,target); gross=convert(line.gross_quantity,line.unit,target)
        return QuantityLine(line.element_id,line.domain,line.item_code,line.description,q,target,line.formula,
                            line.source_id,line.waste_rate,gross,dict(line.metadata))

def validate_quantity_lines(lines:Iterable[QuantityLine]):
    rows=list(lines); errors=[]; ids=set(); sources=set()
    for line in rows:
        if line.element_id in ids: errors.append(f"duplicate element_id: {line.element_id}")
        ids.add(line.element_id)
        if line.source_id and line.source_id in sources: errors.append(f"duplicate source_id: {line.source_id}")
        if line.source_id: sources.add(line.source_id)
        if line.gross_quantity < line.quantity: errors.append(f"gross below net: {line.element_id}")
        if not str(line.source_id).strip(): errors.append(f"missing source_id: {line.element_id}")
    return {"ok":not errors,"errors":errors,"count":len(rows)}
