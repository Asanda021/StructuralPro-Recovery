from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class BIMObject:
    global_id: str
    ifc_type: str
    name: str
    properties: dict[str, Any]

class BIMAdapter:
    def read_ifc(self, path: str | Path) -> list[BIMObject]:
        p=Path(path)
        if not p.exists(): raise FileNotFoundError(p)
        try: import ifcopenshell
        except ImportError as exc: raise RuntimeError("Install ifcopenshell to read IFC offline") from exc
        model=ifcopenshell.open(str(p)); objects=[]
        for obj in model.by_type("IfcProduct"):
            objects.append(BIMObject(obj.GlobalId,obj.is_a(),getattr(obj,"Name",None) or "",{"ObjectType":getattr(obj,"ObjectType",None)}))
        return objects
    @staticmethod
    def count_by_type(objects: list[BIMObject]) -> dict[str,int]:
        out={}
        for obj in objects: out[obj.ifc_type]=out.get(obj.ifc_type,0)+1
        return out
