"""IFC/BIM quantity extraction with optional local IfcOpenShell support."""
from __future__ import annotations
from typing import Any, Iterable
from pathlib import Path
import math

def _quantity_value(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}")
    try:
        number=float(value)
    except (TypeError,ValueError) as exc:
        raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"مقدار کمیت IFC باید متناهی و نامنفی باشد: {name}")
    return number

def classify_objects(objects:Iterable[Any])->dict[str,int]:
    out={}
    for o in objects:
        k=str(getattr(o,"ifc_type",None) or getattr(o,"type",None) or "Unknown")
        out[k]=out.get(k,0)+1
    return out

def extract_quantities(objects:Iterable[Any])->list[dict[str,Any]]:
    rows=[]; seen=set()
    for o in objects:
        gid=str(getattr(o,"global_id","") or "")
        if not gid.strip(): raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in seen: raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        seen.add(gid)
        props=dict(getattr(o,"properties",{}) or {}); q={}
        for k in ("Length","Width","Height","Area","Volume","NetVolume","GrossVolume","Count"):
            if k in props:
                q[k]=_quantity_value(k,props[k])
        rows.append({"global_id":gid,"ifc_type":getattr(o,"ifc_type",""),
                     "name":getattr(o,"name",""),"quantities":q})
    return rows

def read_ifc(path:str|Path)->list[dict[str,Any]]:
    try: import ifcopenshell
    except ImportError as exc: raise RuntimeError("Install ifcopenshell for local IFC parsing") from exc
    model=ifcopenshell.open(str(path)); rows=[]; seen=set()
    for obj in model.by_type("IfcProduct"):
        gid=str(getattr(obj,"GlobalId","") or "")
        if not gid.strip(): raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in seen: raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        seen.add(gid)
        q={}
        for rel in getattr(obj,"IsDefinedBy",[]) or []:
            definition=getattr(rel,"RelatingPropertyDefinition",None)
            for prop in getattr(definition,"Quantities",[]) or []:
                name=str(getattr(prop,"Name","") or "").strip()
                if not name: raise ValueError("نام کمیت IFC نامشخص است")
                for attr in ("LengthValue","AreaValue","VolumeValue","CountValue"):
                    value=getattr(prop,attr,None)
                    if value is not None:
                        if name in q: raise ValueError(f"نام کمیت IFC تکراری است: {name}")
                        q[name]=_quantity_value(name,value); break
        rows.append({"global_id":gid,"ifc_type":obj.is_a(),"name":getattr(obj,"Name","") or "",
                     "quantities":q})
    return rows

def link_2d_3d(two_d:Iterable[dict[str,Any]],three_d:Iterable[dict[str,Any]])->list[dict[str,Any]]:
    by_id={}; out=[]
    for x in three_d:
        gid=str(x.get("global_id") or "")
        if not gid: raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in by_id: raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        by_id[gid]=x
    for x in two_d:
        m=by_id.get(str(x.get("global_id",""))); out.append({"two_d":x,"three_d":m,"linked":m is not None})
    return out

