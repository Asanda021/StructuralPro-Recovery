"""Professional project structure shared by desktop and future clients."""
from __future__ import annotations
from dataclasses import dataclass,field,asdict

@dataclass
class ProjectModel:
    project_id:str; name:str; client:str=""; contractor:str=""; consultant:str=""; contract_number:str=""; location:str=""
    floors:list[dict]=field(default_factory=list); drawings:list[dict]=field(default_factory=list); takeoffs:list[dict]=field(default_factory=list)
    boq:list[dict]=field(default_factory=list); estimates:list[dict]=field(default_factory=list); reports:list[dict]=field(default_factory=list)
    def validate(self):
        errors=[]
        if not self.project_id.strip(): errors.append("شناسه پروژه الزامی است")
        if not self.name.strip(): errors.append("نام پروژه الزامی است")
        ids=set()
        for d in self.drawings:
            did=str(d.get("id",""))
            if did and did in ids: errors.append(f"شناسه نقشه تکراری: {did}")
            ids.add(did)
        return errors
    def add_floor(self,name,level=None):
        item={"id":str(level if level is not None else len(self.floors)+1),"name":str(name)}
        self.floors.append(item); return item
    def add_drawing(self,path,name="",floor_id=None):
        item={"id":f"D{len(self.drawings)+1:04d}","path":str(path),"name":name or str(path),"floor_id":floor_id}
        self.drawings.append(item); return item
    def to_dict(self): return asdict(self)
