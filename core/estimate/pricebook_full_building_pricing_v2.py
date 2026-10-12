from __future__ import annotations
from dataclasses import dataclass
import math
from core.estimate.item_code_normalization_v1 import code_key
DISCIPLINES=("ابنیه","تاسیسات مکانیکی","تاسیسات برقی","مرمت بناهای تاریخی")

def _finite_nonnegative(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be finite and non-negative") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return number

def _finite_total(quantity, unit_price):
    total = quantity * unit_price
    if not math.isfinite(total):
        raise ValueError("price total must be finite")
    return total

@dataclass(frozen=True)
class ProductionRow:
    year:int; discipline:str; item_code:str; description:str; unit:str; unit_price:float; source_sha256:str; source_file:str
def normalize_rows(rows):
    out=[]
    for r in rows:
        code,unit=code_key(r.item_code,r.unit)
        unit_price = _finite_nonnegative(r.unit_price, "unit price")
        if not code or not unit or not r.description or not r.source_sha256: raise ValueError("invalid production pricebook row")
        if r.discipline not in DISCIPLINES: raise ValueError("unsupported building discipline")
        out.append(ProductionRow(int(r.year),r.discipline,code,r.description,unit,unit_price,r.source_sha256,r.source_file))
    return tuple(out)
def price_full_building(takeoff_rows,pricebook_rows,year,discipline):
    rows=normalize_rows(pricebook_rows); index={}
    for r in rows:
        if r.year==year and r.discipline==discipline:
            k=code_key(r.item_code,r.unit)
            if k in index and index[k].unit_price!=r.unit_price: raise ValueError("conflicting code/unit price")
            index[k]=r
    if not index: raise ValueError("pricebook discipline/year dataset is empty")
    priced=[]; unresolved=[]
    for item in takeoff_rows:
        row=index.get(code_key(item.get("item_code"),item.get("unit")))
        if row is None: unresolved.append(str(item.get("takeoff_id",""))); continue
        qty=_finite_nonnegative(item["quantity"], "takeoff quantity")
        total=_finite_total(qty,row.unit_price)
        priced.append({"takeoff_id":str(item["takeoff_id"]),"year":year,"discipline":discipline,"item_code":row.item_code,"unit":row.unit,"quantity":qty,"unit_price":row.unit_price,"total":total,"source_sha256":row.source_sha256,"source_file":row.source_file})
    if unresolved: raise ValueError("unresolved production pricebook rows: "+",".join(unresolved))
    return tuple(priced)


def price_full_building_project(takeoff_rows, pricebook_rows, year):
    """Price a complete multi-discipline building takeoff fail-closed."""
    normalized = normalize_rows(pricebook_rows)
    by_key = {}
    for row in normalized:
        if row.year != int(year):
            continue
        key = (row.discipline, code_key(row.item_code, row.unit))
        previous = by_key.get(key)
        if previous is not None and previous.unit_price != row.unit_price:
            raise ValueError("conflicting code/unit price")
        by_key[key] = row
    if not by_key:
        raise ValueError("pricebook year dataset is empty")
    priced, unresolved = [], []
    for item in takeoff_rows:
        key = (str(item.get("discipline", "")), code_key(item.get("item_code"), item.get("unit")))
        row = by_key.get(key)
        if row is None:
            unresolved.append(str(item.get("takeoff_id", "")))
            continue
        qty = _finite_nonnegative(item["quantity"], "takeoff quantity")
        total = _finite_total(qty, row.unit_price)
        priced.append({"takeoff_id":str(item["takeoff_id"]),"year":int(year),"discipline":row.discipline,"item_code":row.item_code,"unit":row.unit,"quantity":qty,"unit_price":row.unit_price,"total":total,"source_sha256":row.source_sha256,"source_file":row.source_file})
    if unresolved:
        raise ValueError("unresolved production pricebook rows: "+",".join(unresolved))
    return tuple(priced)
