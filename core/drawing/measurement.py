"""Drawing geometry and scale integrity layer."""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot,isfinite
from typing import Iterable,Mapping
_LENGTH_TO_M={"m":1.0,"meter":1.0,"metre":1.0,"mm":0.001,"millimeter":0.001,"millimetre":0.001,"cm":0.01,"centimeter":0.01,"centimetre":0.01,"ft":0.3048,"in":0.0254}
@dataclass(frozen=True)
class DrawingScale:
    unit:str; factor_to_m:float; scale_denominator:float=1.0; source:str="explicit"
    def validate(self):
        if self.unit.casefold().strip() not in _LENGTH_TO_M: raise ValueError(f"unsupported drawing unit: {self.unit!r}")
        if self.factor_to_m<=0 or not isfinite(self.factor_to_m): raise ValueError("factor_to_m must be finite and positive")
        if self.scale_denominator<=0 or not isfinite(self.scale_denominator): raise ValueError("scale_denominator must be finite and positive")
        return self
    @property
    def coordinate_to_m(self): return self.factor_to_m*self.scale_denominator
@dataclass(frozen=True)
class Measurement:
    value:float; unit:str; source_ids:tuple[str,...]; formula:str; warnings:tuple[str,...]=()
    def validate(self):
        if not isfinite(self.value) or self.value<0: raise ValueError("measurement value must be finite and non-negative")
        return self
def scale_from_unit(unit:str,scale_denominator:float=1.0,source:str="explicit"):
    key=unit.casefold().strip()
    if key not in _LENGTH_TO_M: raise ValueError(f"unsupported drawing unit: {unit!r}")
    return DrawingScale(key,_LENGTH_TO_M[key],scale_denominator,source).validate()
def line_length(x,y,x2,y2,scale):
    return Measurement(hypot(x2-x,y2-y)*scale.coordinate_to_m,"m",(),"sqrt((x2-x)^2+(y2-y)^2) × coordinate_to_m").validate()
def primitive_measurements(primitives:Iterable,scale):
    scale.validate(); out=[]
    for p in primitives:
        kind=p.normalized_kind(); source=(p.source_id,) if p.source_id else ()
        if kind in {"line","polyline"}:
            m=line_length(p.x,p.y,p.x2,p.y2,scale); out.append(Measurement(m.value,m.unit,source,m.formula,m.warnings))
        elif kind=="circle" and p.width>0:
            out.append(Measurement(p.width*scale.coordinate_to_m,"m",source,"circle diameter × coordinate_to_m").validate())
        elif p.width>0 and p.height>0:
            out.append(Measurement(p.width*scale.coordinate_to_m,"m",source,"width × coordinate_to_m").validate())
    return tuple(out)
def scale_from_metadata(metadata:Mapping[str,object]):
    unit=metadata.get("unit") or metadata.get("units")
    if not isinstance(unit,str) or not unit.strip(): return None
    raw=metadata.get("scale_denominator")
    if raw is None: raise ValueError("drawing scale denominator is missing")
    try: denominator=float(raw)
    except (TypeError,ValueError): raise ValueError("scale_denominator must be numeric")
    return scale_from_unit(unit,denominator,"source-metadata")
