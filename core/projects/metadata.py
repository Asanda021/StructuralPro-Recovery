"""Structured project metadata and validation for construction projects."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
import re

@dataclass
class ProjectMetadata:
    project_id:str
    name:str
    client:str=""
    contractor:str=""
    consultant:str=""
    contract_number:str=""
    location:str=""
    area_m2:float|None=None
    floors:int|None=None
    start_date:str=""
    end_date:str=""
    description:str=""

    def validate(self)->list[str]:
        e=[]
        if not self.project_id.strip(): e.append("project_id_required")
        if not self.name.strip(): e.append("name_required")
        if self.area_m2 is not None and self.area_m2<0: e.append("area_m2_invalid")
        if self.floors is not None and self.floors<0: e.append("floors_invalid")
        for field in ("start_date","end_date"):
            value=getattr(self,field)
            if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value): e.append(f"{field}_invalid")
        return e

    def to_dict(self): return asdict(self)

    @classmethod
    def from_dict(cls,data): return cls(**{f:data.get(f,getattr(cls,f,"")) for f in cls.__dataclass_fields__})
