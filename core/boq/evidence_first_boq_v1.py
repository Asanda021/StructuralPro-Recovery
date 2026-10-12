"""P421-P430 evidence-first BOQ boundary."""
from dataclasses import dataclass
from hashlib import sha256
import json, math

@dataclass(frozen=True)
class EvidenceBOQLine:
    line_id:str
    quantity_id:str
    source_ids:tuple[str,...]
    description:str
    quantity:float
    unit:str
    revision:str
    status:str="accepted"
    def validate(self):
        if not all((self.line_id,self.quantity_id,self.description,self.unit,self.revision)): raise ValueError("incomplete BOQ evidence")
        if not self.source_ids: raise ValueError("source evidence required")
        if not math.isfinite(float(self.quantity)) or self.quantity<0: raise ValueError("invalid quantity")
        if self.status!="accepted": raise ValueError("only accepted evidence may enter BOQ")
        return self

def fingerprint(lines):
    data=[x.validate().__dict__ for x in sorted(lines,key=lambda z:z.line_id)]
    return sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def build(lines):
    for x in lines: x.validate()
    return tuple(sorted(lines,key=lambda z:z.line_id))
