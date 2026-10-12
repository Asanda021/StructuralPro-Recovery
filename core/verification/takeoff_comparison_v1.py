from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class Comparison:
    project_id: str
    item_code: str
    unit: str
    reference: float
    system: float
    tolerance: float

def compare(rows):
    if not rows: raise ValueError("reference evidence required")
    errors=[]; passed=0
    for x in rows:
        if not all((x.project_id,x.item_code,x.unit)): raise ValueError("incomplete evidence")
        if min(x.reference,x.system,x.tolerance)<0: raise ValueError("negative value")
        if x.reference==0 and x.system!=0: raise ValueError("invalid zero reference")
        e=0 if x.reference==0 else abs(x.system-x.reference)/x.reference
        errors.append(e); passed += e <= x.tolerance
    payload="|".join(sorted(f"{x.project_id}|{x.item_code}|{x.unit}|{x.reference}|{x.system}|{x.tolerance}" for x in rows))
    return {"count":len(rows),"passed":passed,"failed":len(rows)-passed,"mean_relative_error":sum(errors)/len(errors),"decision":"accepted" if passed==len(rows) else "review","fingerprint":sha256(payload.encode()).hexdigest()}
