"""P101 — fail-closed scaled mapping/pricing across normalized rows."""
from __future__ import annotations
from dataclasses import dataclass
from core.estimate.item_code_normalization_v1 import code_key

@dataclass(frozen=True)
class ScaleResult:
    total:int
    priced:int
    unresolved:tuple
    conflicts:tuple

def build_index(rows,year,discipline):
    idx={}
    conflicts=[]
    for r in rows:
        if r.year!=year or r.discipline!=discipline: continue
        k=code_key(r.item_code,r.unit)
        if k in idx and idx[k].unit_price!=r.unit_price:
            conflicts.append(k)
        idx[k]=r
    if conflicts: raise ValueError("pricebook code/unit conflicts: "+str(sorted(set(conflicts))))
    return idx

def price_rows(takeoff_rows,normalized_rows,year,discipline):
    idx=build_index(normalized_rows,year,discipline); unresolved=[]; priced=[]
    for item in takeoff_rows:
        k=code_key(item.get("item_code"),item.get("unit"))
        row=idx.get(k)
        if row is None: unresolved.append(str(item.get("takeoff_id","")))
        else:
            qty=float(item["quantity"])
            if qty<0: raise ValueError("negative takeoff quantity")
            if row.unit_price is None:
                raise ValueError(f"unpriced pricebook row: {row.item_code}/{row.unit}")
            priced.append({"takeoff_id":str(item["takeoff_id"]),"item_code":row.item_code,
                           "unit":row.unit,"quantity":qty,"unit_price":row.unit_price,
                           "total":qty*row.unit_price})
    if unresolved: raise ValueError("unresolved pricebook rows: "+",".join(unresolved))
    return tuple(priced)

def scale_gate(takeoff_rows,normalized_rows,year,discipline):
    priced=price_rows(takeoff_rows,normalized_rows,year,discipline)
    return ScaleResult(len(takeoff_rows),len(priced),(),())
