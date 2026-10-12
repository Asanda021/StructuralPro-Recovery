"""P461-P470 deterministic cost/project-control evidence boundary."""
from dataclasses import dataclass
from hashlib import sha256
import json,math
@dataclass(frozen=True)
class CostRecord:
    record_id:str
    source_ids:tuple[str,...]
    amount:float
    currency:str
    revision:str
    status:str="accepted"
    def validate(self):
        if not self.record_id or not self.source_ids or not self.currency or not self.revision: raise ValueError("incomplete cost evidence")
        if not math.isfinite(float(self.amount)) or self.amount<0: raise ValueError("invalid amount")
        if self.status!="accepted": raise ValueError("review required")
        return self
def fingerprint(rows):
    return sha256(json.dumps([r.validate().__dict__ for r in sorted(rows,key=lambda x:x.record_id)],sort_keys=True,separators=(",",":")).encode()).hexdigest()
