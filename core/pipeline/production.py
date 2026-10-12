"""End-to-end production pipeline from drawing/model quantities to BOQ and estimate."""
from __future__ import annotations
from typing import Iterable, Mapping
from core.validation.real_data import validate_project

def build_production_package(*, takeoffs:Iterable[Mapping], boq:Iterable[Mapping], estimate:Mapping|None=None, project_id="P"):
    project={"id":str(project_id),"name":str(project_id),"takeoffs":[dict(x) for x in takeoffs],
             "boq":[dict(x) for x in boq],"estimate":dict(estimate or {})}
    validation=validate_project(project)
    if not validation["valid"]: raise ValueError({"validation":validation})
    totals={"quantity":sum(float(x.get("quantity",0) or 0) for x in project["boq"]),
            "amount":sum(float(x.get("total",0) or 0) for x in project["boq"])}
    return {"project":project,"validation":validation,"totals":totals,"ready":True}
