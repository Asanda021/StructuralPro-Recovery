"""Professional project structure shared by desktop and future clients."""
from __future__ import annotations
from dataclasses import dataclass,field,asdict
import unicodedata

_ID_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def _identity(value):
    """Compare identifiers without changing their stored spelling."""
    if value is None or isinstance(value, bool): return ""
    return (unicodedata.normalize("NFKC", str(value))
            .translate(_ID_DIGITS).replace("ي", "ی").replace("ك", "ک")
            .strip().casefold())

@dataclass
class ProjectModel:
    project_id:str; name:str; client:str=""; contractor:str=""; consultant:str=""; contract_number:str=""; location:str=""
    floors:list[dict]=field(default_factory=list); drawings:list[dict]=field(default_factory=list); takeoffs:list[dict]=field(default_factory=list)
    boq:list[dict]=field(default_factory=list); estimates:list[dict]=field(default_factory=list); reports:list[dict]=field(default_factory=list)
    members:list[dict]=field(default_factory=list)
    def validate(self):
        errors=[]
        if not _identity(self.project_id): errors.append("شناسه پروژه الزامی است")
        if not isinstance(self.name,str) or not self.name.strip(): errors.append("نام پروژه الزامی است")
        floor_ids=set()
        for floor in self.floors:
            if not isinstance(floor,dict):
                errors.append("اطلاعات طبقه باید ساختار معتبر داشته باشد");continue
            key=_identity(floor.get("id"))
            if not key: errors.append("شناسه طبقه الزامی است")
            elif key in floor_ids: errors.append(f"شناسه طبقه تکراری: {floor.get('id')}")
            else: floor_ids.add(key)
            if not isinstance(floor.get("name"),str) or not floor["name"].strip():
                errors.append("نام طبقه الزامی است")
        member_ids=set()
        for member in self.members:
            if not isinstance(member,dict):
                errors.append("اطلاعات عضو باید ساختار معتبر داشته باشد");continue
            key=_identity(member.get("id"))
            if not key: errors.append("شناسه عضو الزامی است")
            elif key in member_ids: errors.append(f"شناسه عضو تکراری: {member.get('id')}")
            else: member_ids.add(key)
            if not _identity(member.get("floor_id")) or _identity(member.get("floor_id")) not in floor_ids:
                errors.append(f"طبقه عضو موجود نیست: {member.get('floor_id')}")
            if not _identity(member.get("kind")): errors.append("نوع عضو الزامی است")
        ids=set()
        for drawing in self.drawings:
            if not isinstance(drawing,dict):
                errors.append("اطلاعات نقشه باید ساختار معتبر داشته باشد");continue
            did=str(drawing.get("id",""))
            if did and did in ids: errors.append(f"شناسه نقشه تکراری: {did}")
            ids.add(did)
        return errors

    def add_floor(self,name,level=None):
        if not isinstance(name,str) or not name.strip(): raise ValueError("نام طبقه الزامی است")
        existing={_identity(f.get("id")) for f in self.floors if isinstance(f,dict)}
        if level is None:
            next_number=1
            while _identity(next_number) in existing: next_number+=1
            floor_id=str(next_number)
        else:
            floor_id=str(level) if not isinstance(level,bool) else ""
        if not _identity(floor_id) or _identity(floor_id) in existing:
            raise ValueError("شناسه طبقه خالی یا تکراری است")
        item={"id":floor_id,"name":name.strip()}
        self.floors.append(item);return item

    def add_member(self,member_id,floor_id,kind,*,source_id=None):
        """Register member identity only; no geometry or payable quantity is inferred."""
        key=_identity(member_id)
        if not key or key in {_identity(m.get("id")) for m in self.members if isinstance(m,dict)}:
            raise ValueError("شناسه عضو خالی یا تکراری است")
        target=_identity(floor_id)
        floors={_identity(f.get("id")):f for f in self.floors if isinstance(f,dict)}
        if not target or target not in floors: raise ValueError("طبقه عضو موجود نیست")
        if not _identity(kind): raise ValueError("نوع عضو الزامی است")
        if source_id is not None and not _identity(source_id): raise ValueError("شناسه مدرک نامعتبر است")
        item={"id":str(member_id).strip(),"floor_id":floors[target]["id"],"kind":str(kind).strip()}
        if source_id is not None: item["source_id"]=str(source_id).strip()
        self.members.append(item);return item

    def add_drawing(self,path,name="",floor_id=None):
        item={"id":f"D{len(self.drawings)+1:04d}","path":str(path),"name":name or str(path),"floor_id":floor_id}
        self.drawings.append(item); return item
    def to_dict(self): return asdict(self)
