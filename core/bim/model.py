"""Canonical BIM entities for IFC-driven takeoff."""
from dataclasses import dataclass,field
from typing import Mapping
@dataclass(frozen=True)
class BIMElement:
    global_id:str; ifc_type:str; name:str=""; domain:str="bim"; kind:str="unknown"
    level:str|None=None; type_name:str|None=None; material_names:tuple[str,...]=()
    properties:Mapping[str,object]=field(default_factory=dict)
    geometry:Mapping[str,float]=field(default_factory=dict)
    source_id:str=""
    @property
    def has_quantity_geometry(self):
        return bool(self.geometry) and any(v is not None for v in self.geometry.values())

    @property
    def has_explicit_quantity_geometry(self):
        return any(str(k).casefold() in {"volume","netvolume","grossvolume","area"} and v is not None
                   for k,v in self.geometry.items())
