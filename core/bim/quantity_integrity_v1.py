"""Fail-closed BIM quantity normalization and lineage integrity."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json, math
@dataclass(frozen=True)
class BIMQuantityEvidence:
    global_id:str; source_id:str; item_code:str; quantity:float; unit:str
    def validate(self):
        q=float(self.quantity)
        if not self.global_id.strip() or not self.source_id.strip() or not self.item_code.strip() or not self.unit.strip(): raise ValueError("BIM quantity identity is incomplete")
        if not math.isfinite(q) or q<0: raise ValueError("BIM quantity must be finite and non-negative")
        return self
def normalize_quantities(rows):
    out=[]
    seen=set()
    for r in rows:
        e=BIMQuantityEvidence(str(r.global_id),str(r.source_id),str(r.item_code),float(r.quantity),str(r.unit)).validate()
        if e.global_id in seen: raise ValueError("duplicate BIM GlobalId")
        seen.add(e.global_id); out.append(e)
    return tuple(out)
def fingerprint(rows):
    data=[asdict(x.validate()) for x in normalize_quantities(rows)]
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()
