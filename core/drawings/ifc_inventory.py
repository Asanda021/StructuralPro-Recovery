"""IFC inventory, quantity mapping and duplicate-safe price mapping."""
from __future__ import annotations
from typing import Any, Iterable

def inventory(rows):
    rows=list(rows); by_type={}; by_level={}; totals={}; ids=set(); duplicates=[]
    for r in rows:
        gid=str(r.get("global_id") or "")
        if gid and gid in ids: duplicates.append(gid)
        if gid: ids.add(gid)
        typ=str(r.get("ifc_type") or "Unknown"); by_type[typ]=by_type.get(typ,0)+1
        props=r.get("properties") or {}; level=str(props.get("Level") or props.get("Storey") or r.get("level") or "بدون طبقه")
        by_level[level]=by_level.get(level,0)+1
        for k,v in (r.get("quantities") or {}).items():
            try: totals[k]=totals.get(k,0)+float(v)
            except (TypeError,ValueError): pass
    return {"objects":len(rows),"unique_objects":len(ids),"duplicates":duplicates,"by_type":by_type,"by_level":by_level,"quantity_totals":totals}

def normalize_bim_rows(rows):
    out=[]; seen=set()
    for r in rows:
        gid=str(r.get("global_id") or "")
        if gid and gid in seen: continue
        if gid: seen.add(gid)
        props=r.get("properties") or {}
        q={}
        for k,v in (r.get("quantities") or {}).items():
            try:q[str(k)]=float(v)
            except (TypeError,ValueError): pass
        out.append({"global_id":gid,"ifc_type":str(r.get("ifc_type") or ""),"name":str(r.get("name") or ""),
                    "level":str(props.get("Level") or props.get("Storey") or r.get("level") or ""),
                    "properties":dict(props),"quantities":q})
    return out

def map_bim_to_price(rows,mapping,*,strict=False):
    out=[]; unmapped=[]
    for r in rows:
        code=mapping.get(r.get("ifc_type")) or mapping.get("default")
        if code: out.append({**r,"price_code":code,"mapping_status":"mapped"})
        else:
            unmapped.append(r.get("global_id","")); 
            if not strict: out.append({**r,"price_code":None,"mapping_status":"unmapped"})
    if strict and unmapped: raise ValueError("Unmapped IFC objects: "+",".join(map(str,unmapped[:10])))
    return out
