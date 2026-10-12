"""Product-level orchestration for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from copy import deepcopy
from typing import Any, Callable, Iterable, Mapping
from .parity import capability_matrix
from .capability_bindings import build_bindings

@dataclass(frozen=True)
class FeatureAction:
    capability_id:str
    action:str
    description:str
    kind:str="core"
    handler:Callable[...,Any]|None=field(default=None,compare=False,repr=False)
    def run(self,*args,**kwargs):
        if self.handler is None:
            raise NotImplementedError(f"برای قابلیت {self.capability_id} هنوز آداپتور اجرایی متصل نشده است.")
        return self.handler(*args,**kwargs)

class ProductHub:
    def __init__(self,project_service=None,pricing=None,sync=None):
        self.project_service=project_service; self.pricing=pricing; self.sync=sync
        self._actions={}; self._register_contracts()

    def _register(self,capability_id,action,description,handler=None,kind="core"):
        self._actions[capability_id]=FeatureAction(capability_id,action,description,kind,handler)

    def _register_contracts(self):
        bindings=build_bindings()
        for cap in capability_matrix():
            self._register(cap["id"],cap["id"],cap["title"],bindings.get(cap["id"]),cap["category"])

    def capabilities(self):
        return [{"id":a.capability_id,"action":a.action,"description":a.description,"kind":a.kind,
                 "has_handler":a.handler is not None} for a in self._actions.values()]

    def get(self,capability_id):
        if capability_id not in self._actions: raise KeyError(f"قابلیت ناشناخته: {capability_id}")
        return self._actions[capability_id]

    def set_handler(self,capability_id,handler):
        old=self.get(capability_id)
        self._actions[capability_id]=FeatureAction(old.capability_id,old.action,old.description,old.kind,handler)

    def validate_project(self,project:Mapping[str,Any]):
        issues=[]
        if not str(project.get("name","")).strip():
            issues.append({"code":"missing_project_name","severity":"error","message":"نام پروژه وارد نشده است."})
        for i,takeoff in enumerate(project.get("takeoffs",[]) or []):
            member=takeoff.get("member_code") or f"ردیف {i+1}"
            for q in takeoff.get("quantities",[]) or []:
                try: value=float(q.get("amount"))
                except (TypeError,ValueError):
                    issues.append({"code":"invalid_quantity","severity":"error","member":member,"message":"مقدار معتبر نیست."}); continue
                if value<0: issues.append({"code":"negative_quantity","severity":"error","member":member,"message":"مقدار منفی مجاز نیست."})
                if not q.get("unit"): issues.append({"code":"missing_unit","severity":"warning","member":member,"message":"واحد مشخص نشده است."})
        return issues

    def apply_bulk(self,project:Mapping[str,Any],changes:Mapping[str,Any],member_codes:Iterable[str]|None=None):
        result=deepcopy(dict(project)); wanted=set(member_codes or [])
        for takeoff in result.get("takeoffs",[]) or []:
            if wanted and takeoff.get("member_code") not in wanted: continue
            takeoff.update(deepcopy(dict(changes)))
        result["updated_at"]=datetime.now().isoformat(timespec="seconds")
        return result

    def duplicate_takeoff(self,project:Mapping[str,Any],member_code:str,copies:int=1):
        result=deepcopy(dict(project)); rows=result.setdefault("takeoffs",[])
        source=next((x for x in rows if x.get("member_code")==member_code),None)
        if source is None: raise KeyError(f"عضو {member_code} پیدا نشد.")
        import uuid
        for _ in range(max(0,int(copies))):
            clone=deepcopy(source); clone["id"]=uuid.uuid4().hex; clone["member_code"]=f"{member_code}-{len(rows)+1}"; rows.append(clone)
        result["updated_at"]=datetime.now().isoformat(timespec="seconds"); return result

    def summary(self):
        matrix=capability_matrix(); implemented=sum(x["status"]=="implemented" for x in matrix)
        contract=sum(x["status"]=="contract" for x in matrix)
        return {"total_capabilities":len(matrix),"implemented_capabilities":implemented,
                "contract_capabilities":contract,"coverage_percent":round((implemented+contract)*100/len(matrix),1),
                "catalog_version":"1.0","clients":["windows","android-contract","telegram-contract"],
                "offline_core":True,"local_ai":True,"cloud_optional":True,"registered":len(self._actions),
                "generated_at":datetime.now().isoformat(timespec="seconds")}
