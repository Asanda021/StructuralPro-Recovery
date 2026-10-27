"""Project-scoped global search with Persian normalization and provenance.

This is an extension of the original search_project API, not a second index
or a financial/engineering source of truth. Callers must first pass the
authorized project snapshot from ProjectStore.get().
"""
from __future__ import annotations
import re
import unicodedata
from typing import Any

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize(value: Any) -> str:
    if not isinstance(value,(str,int,float)):
        return ""
    text=unicodedata.normalize("NFKC",str(value)).translate(_DIGITS)
    text=text.replace("ي","ی").replace("ك","ک").replace("\u200c","").casefold()
    return re.sub(r"\s+"," ",text).strip()


def search_project(project, query, *, limit=100):
    """Read only stored fields; never infer a geometry/identity or use another project."""
    if not isinstance(project,dict):
        return []
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=1000:
        raise ValueError("حد مجاز نتایج جست‌وجو نامعتبر است.")
    q=normalize(query)
    if not q:return []
    pid=project.get("id")
    results=[]
    seen=set()
    def hit(kind,text,data,*,entity_id=None,source_id=None,revision=None,route=None):
        label=str(text or "").strip()
        if not label or q not in normalize(label):return
        # Stable record position is for display only, not a fabricated identity.
        identity=str(entity_id) if entity_id is not None else None
        key=(kind,identity,label,id(data) if identity is None else None)
        if key in seen:return
        seen.add(key)
        results.append({
            "kind":kind,"text":label,"data":data,
            "project_id":pid,"entity_id":identity,
            "source_id":source_id,"revision":revision,
            "route":route,
            "link_status":"source_record" if identity is not None else "unindexed_record",
        })
    def rec(kind,record,*,keys,route):
        if not isinstance(record,dict):return
        idvalue=next((record[k] for k in ("id","row_id","member_id","system_id")
                      if record.get(k) not in (None,"")),None)
        source=record.get("source_id") or record.get("source_ids")
        rev=record.get("revision")
        for key in keys:
            val=record.get(key)
            if val is not None and not isinstance(val,(dict,list,tuple)):
                hit(kind,val,record,entity_id=idvalue,source_id=source,revision=rev,route=route)
    def rows(container):
        if isinstance(container,list):return container
        if isinstance(container,dict):return list(container.values())
        return []
    hit("project",project.get("name",""),project,entity_id=pid,route="projects")
    hit("project",pid,project,entity_id=pid,route="projects")
    for x in rows(project.get("floors")):
        rec("floor",x,keys=("id","name","level"),route="projects")
    for x in rows(project.get("members")):
        rec("member",x,keys=("id","kind","floor_id","title"),route="projects")
    for x in rows(project.get("drawings"))+rows(project.get("documents")):
        rec("drawing",x,keys=("id","name","title","path","source_id"),route="drawing")
    for t in rows(project.get("takeoffs")):
        rec("takeoff",t,keys=("id","title","description","item","source_id"),route="takeoff")
        for item in rows(t.get("quantities")):
            rec("item",item,keys=("title","description","price_code","code"),route="takeoff")
            rec("price_code",item,keys=("price_code",),route="prices")
    for row in rows(project.get("boq")):
        rec("boq",row,keys=("description","title","item_code","price_code","item_no"),route="boq")
        rec("price_code",row,keys=("price_code",),route="prices")
    for key in ("wbs","activities","work_packages","project_schedule_tasks","project_wbs"):
        for row in rows(project.get(key)):
            rec("wbs",row,keys=("id","title","name","wbs_id"),route="project_controls")
    for row in rows(project.get("reports")):
        rec("report",row,keys=("id","title","name","path"),route="reports")
    for row in rows(project.get("manual_formula_register")):
        if isinstance(row,dict):
            d=row.get("data",{})
            if isinstance(d,dict):
                rec("item",d,keys=("title","member","source_id","family"),route="takeoff")
    return results[:limit]
