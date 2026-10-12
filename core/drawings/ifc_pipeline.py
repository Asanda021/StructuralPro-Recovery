"""Deep IFC/BIM normalization: spatial level, properties, quantities and duplicate safety."""
from __future__ import annotations
from typing import Any, Iterable
import math

QUANTITY_UNITS={"Length":"m","Width":"m","Height":"m","Area":"m2","NetArea":"m2",
                "GrossArea":"m2","Volume":"m3","NetVolume":"m3","GrossVolume":"m3","Count":"عدد"}

def normalize_ifc_rows(rows:Iterable[dict[str,Any]])->list[dict[str,Any]]:
    out=[]; seen=set()
    for r in rows:
        gid=str(r.get("global_id") or "")
        if not gid.strip():
            raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in seen:
            raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        seen.add(gid)
        props=dict(r.get("properties") or {})
        quantities={}
        for k,v in dict(r.get("quantities") or {}).items():
            name=str(k).strip()
            if not name or name not in QUANTITY_UNITS:
                raise ValueError(f"نوع یا واحد کمیت IFC پشتیبانی نمی‌شود: {name or '<empty>'}")
            if isinstance(v, bool):
                raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}")
            try:
                value=float(v)
            except (TypeError,ValueError) as exc:
                raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}") from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"مقدار کمیت IFC باید متناهی و نامنفی باشد: {name}")
            quantities[name]=value
        level=str(r.get("level") or props.get("Level") or props.get("Storey") or props.get("BuildingStorey") or "")
        out.append({"global_id":gid,"ifc_type":str(r.get("ifc_type") or ""),
                    "name":str(r.get("name") or ""), "level":level,
                    "properties":props,"quantities":quantities,
                    "quantity_units":{k:QUANTITY_UNITS[k] for k in quantities}})
    return out

def aggregate_ifc_quantities(rows:Iterable[dict[str,Any]])->dict[str,Any]:
    rows=normalize_ifc_rows(rows); totals={}; by_type={}; by_level={}
    for r in rows:
        t=r["ifc_type"] or "Unknown"; by_type[t]=by_type.get(t,0)+1
        lv=r["level"] or "بدون طبقه"; by_level[lv]=by_level.get(lv,0)+1
        for k,v in r["quantities"].items(): totals[k]=totals.get(k,0)+v
    return {"objects":len(rows),"by_type":by_type,"by_level":by_level,"quantity_totals":totals}

def map_ifc_to_boq(rows:Iterable[dict[str,Any]],mapping:dict[str,str]):
    result=[]; unmapped=[]
    for r in normalize_ifc_rows(rows):
        code=mapping.get(r["ifc_type"])
        if not code: unmapped.append(r["global_id"] or r["name"]); continue
        for key,value in r["quantities"].items():
            unit=QUANTITY_UNITS.get(key,"")
            result.append({"global_id":r["global_id"],"level":r["level"],"price_code":code,
                           "description":r["name"] or r["ifc_type"],"quantity":value,"unit":unit,
                           "source":f'ifc:{r["global_id"] or r["name"]}:{key}',"needs_confirmation":True})
    return {"rows":result,"unmapped":unmapped}

