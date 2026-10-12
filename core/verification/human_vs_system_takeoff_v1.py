from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class TakeoffComparison:
    project_id:str
    item_code:str
    unit:str
    human_quantity:float
    system_quantity:float
    tolerance:float

@dataclass(frozen=True)
class ComparisonResult:
    item_count:int
    passed_count:int
    failed_count:int
    mean_relative_error:float
    decision:str
    fingerprint:str

def compare(items):
    if not items: raise ValueError("human reference evidence required")
    for x in items:
        if not all((x.project_id.strip(),x.item_code.strip(),x.unit.strip())): raise ValueError("incomplete comparison")
        if x.human_quantity < 0 or x.system_quantity < 0 or x.tolerance < 0: raise ValueError("negative quantity or tolerance")
        if x.human_quantity == 0 and x.system_quantity != 0: raise ValueError("nonzero system quantity against zero human reference")
    errors=[]
    passed=0
    for x in items:
        rel=0.0 if x.human_quantity==x.system_quantity else abs(x.system_quantity-x.human_quantity)/x.human_quantity if x.human_quantity else 0.0
        errors.append(rel)
        if rel <= x.tolerance: passed+=1
    mean=sum(errors)/len(errors)
    decision="accepted" if passed==len(items) else "review"
    payload="|".join(sorted(f"{x.project_id}|{x.item_code}|{x.unit}|{x.human_quantity}|{x.system_quantity}|{x.tolerance}" for x in items))
    return ComparisonResult(len(items),passed,len(items)-passed,mean,decision,sha256(payload.encode()).hexdigest())
