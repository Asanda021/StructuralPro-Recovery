"""Professional deterministic BOQ builder."""
from __future__ import annotations
from typing import Iterable,Any
import math
from .units import normalize_unit
BOQ_DEFAULT_STATUS="active"
def _read(r,name,default=None): return r.get(name,default) if isinstance(r,dict) else getattr(r,name,default)
def _text(value): return str(value or "").strip()
def _number(value,field,*,allow_none=True):
    if value is None and allow_none: return None
    if isinstance(value, bool): raise ValueError(f"{field} must be numeric")
    try: number=float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number): raise ValueError(f"{field} must be finite")
    return number
def build_boq(rows:Iterable[Any],aggregate:bool=True,factor:float=1.0)->list[dict[str,Any]]:
    factor=_number(factor,"factor",allow_none=False)
    if factor<0: raise ValueError("factor must be finite and non-negative")
    raw=[]
    for r in rows:
        source=_text(_read(r,"source","")); source_id=_text(_read(r,"source_id",""))
        source_ids=_read(r,"source_ids",None)
        if source_ids is None: source_ids=[source_id] if source_id else []
        else: source_ids=[_text(x) for x in source_ids if _text(x)]
        source_type=_text(_read(r,"source_type","manual")) or "manual"
        q=_number(_read(r,"quantity",None),"quantity",allow_none=False)
        if q<0: raise ValueError("quantity must be finite and non-negative")
        raw_unit=_text(_read(r,"unit",""))
        if not raw_unit: raise ValueError("unit is required")
        unit=normalize_unit(raw_unit)
        price=_number(_read(r,"unit_price",None),"unit_price")
        if price is not None and price<0: raise ValueError("unit_price must be finite and non-negative")
        code=_text(_read(r,"price_code","")) or None; item_code=_text(_read(r,"item_code","")) or code
        description=_text(_read(r,"description",""))
        if not description: raise ValueError("description is required")
        chapter=_text(_read(r,"chapter","")); category=_text(_read(r,"category","")) or chapter
        group=_text(_read(r,"group","")) or category or "سایر"
        f=_number(_read(r,"factor",factor),"factor",allow_none=False)
        if f<0: raise ValueError("factor must be finite and non-negative")
        status=_text(_read(r,"status",BOQ_DEFAULT_STATUS)) or BOQ_DEFAULT_STATUS
        notes=_text(_read(r,"notes","")); waste_percent=_number(_read(r,"waste_percent",0),"waste_percent",allow_none=False)
        allowance_quantity=_number(_read(r,"allowance_quantity",0),"allowance_quantity",allow_none=False)
        if waste_percent<0 or allowance_quantity<0: raise ValueError("waste/allowance must be finite and non-negative")
        effective_quantity=_number(q*(1+waste_percent/100)+allowance_quantity,"effective_quantity",allow_none=False)
        total=None if price is None else _number(round(effective_quantity*price*f,10),"total",allow_none=False)
        warning="zero_price" if price==0 else ""
        raw.append({"source":source,"source_id":source_id,"source_ids":source_ids,"source_type":source_type,
                    "item_code":item_code,"price_code":code,"chapter":chapter,"category":category,"group":group,
                    "description":description,"quantity":q,"effective_quantity":effective_quantity,
                    "waste_percent":waste_percent,"allowance_quantity":allowance_quantity,"unit":unit,
                    "unit_price":price,"total":total,"factor":f,"status":status,"notes":notes,"warning":warning})
    if aggregate:
        groups={}
        for r in raw:
            key=(r["item_code"] or r["price_code"] or r["description"],
                 r["price_code"], r["description"], r["unit"], r["unit_price"], r["factor"],
                 r["chapter"],r["category"],r["group"],r["status"],
                 r["waste_percent"], r["source_type"])
            if key not in groups: groups[key]=dict(r)
            else:
                groups[key]["quantity"]+=r["quantity"]; groups[key]["effective_quantity"]+=r["effective_quantity"]
                groups[key]["allowance_quantity"]+=r["allowance_quantity"]
                if groups[key]["total"] is not None and r["total"] is not None: groups[key]["total"]+=r["total"]
                elif groups[key]["total"] is None: groups[key]["total"]=r["total"]
                for source_id in r.get("source_ids",[]):
                    if source_id not in groups[key]["source_ids"]: groups[key]["source_ids"].append(source_id)
        raw=list(groups.values())
    return [dict(item_no=i,**r) for i,r in enumerate(raw,1)]
def validate_boq_structure(rows):
    rows=list(rows); errors=[]; warnings=[]; codes=set()
    for index,row in enumerate(rows,1):
        code=_text(row.get("price_code") or row.get("item_code"))
        if not code: warnings.append({"item_no":index,"code":"missing_item_code"})
        elif code in codes: warnings.append({"item_no":index,"code":"duplicate_item_code","value":code})
        codes.add(code)
        if not _text(row.get("description")): errors.append({"item_no":index,"code":"missing_description"})
        if not _text(row.get("unit")): errors.append({"item_no":index,"code":"missing_unit"})
        try:
            q=float(row.get("quantity",0)); eq=float(row.get("effective_quantity",q)); total=row.get("total")
            if not math.isfinite(q) or q<0: errors.append({"item_no":index,"code":"invalid_quantity"})
            if not math.isfinite(eq) or eq<0: errors.append({"item_no":index,"code":"invalid_effective_quantity"})
            if total is not None and (not math.isfinite(float(total)) or float(total)<0): errors.append({"item_no":index,"code":"invalid_total"})
        except (TypeError,ValueError): errors.append({"item_no":index,"code":"invalid_quantity"})
    return {"valid":not errors,"errors":errors,"warnings":warnings,"line_count":len(rows)}
def boq_summary(rows):
    rows=list(rows)
    active=[r for r in rows if r.get("status","active")=="active"]
    return {"line_count":len(rows),"active_line_count":len(active),
            "quantity_by_unit":_sum_by(active,"unit","quantity"),
            "amount_by_code":_sum_by(active,"price_code","total"),
            "amount_by_group":_sum_by(active,"group","total"),
            "grand_total":sum(float(r.get("total") or 0) for r in active),
            "warnings":[r for r in rows if r.get("warning")]}
def _sum_by(rows,key,value):
    out={}
    for r in rows:
        k=r.get(key) or "بدون کد"; out[k]=out.get(k,0)+float(r.get(value) or 0)
    return out
