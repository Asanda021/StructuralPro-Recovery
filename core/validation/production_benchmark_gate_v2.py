from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from pathlib import Path
@dataclass(frozen=True)
class BenchmarkCase:
    case_id:str; item_id:str; reference_quantity:float; system_quantity:float; unit:str; source_ref:str
def load_cases(path:str|Path)->tuple[BenchmarkCase,...]:
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(p)
    raw=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw,list) or not raw: raise ValueError("benchmark dataset must be a non-empty list")
    out=[]
    for x in raw:
        if any(not str(x.get(k,"")).strip() for k in ("case_id","item_id","unit","source_ref")): raise ValueError("missing benchmark identity")
        ref=float(x["reference_quantity"]); system=float(x["system_quantity"])
        if ref<0 or system<0: raise ValueError("benchmark quantities cannot be negative")
        out.append(BenchmarkCase(str(x["case_id"]),str(x["item_id"]),ref,system,str(x["unit"]),str(x["source_ref"])))
    return tuple(out)
def evaluate(cases:tuple[BenchmarkCase,...],tolerance:float=0.02)->dict:
    if not cases: raise ValueError("benchmark requires cases")
    errors=[0.0 if c.reference_quantity==0 and c.system_quantity==0 else 1.0 if c.reference_quantity==0 else abs(c.system_quantity-c.reference_quantity)/c.reference_quantity for c in cases]
    mean=sum(errors)/len(errors); rate=sum(e<=tolerance for e in errors)/len(errors)
    result={"cases":len(cases),"tolerance":tolerance,"mean_relative_error":round(mean,8),"within_tolerance_rate":round(rate,8),"green2":mean<=tolerance and rate>=0.95}
    result["fingerprint"]=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return result
def require_green2(result:dict)->dict:
    if not result.get("green2"): raise ValueError("benchmark is not green2")
    return result
