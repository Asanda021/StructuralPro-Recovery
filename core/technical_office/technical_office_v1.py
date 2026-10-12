"""Technical Office / دفتر فنی: deterministic evidence boundary."""
from dataclasses import dataclass
from hashlib import sha256
import json,math
@dataclass(frozen=True)
class Record:
    record_id:str
    source_ids:tuple[str,...]
    value:float
    unit:str
    revision:str
    status:str="accepted"
    def validate(self):
        if not self.record_id or not self.source_ids or not self.unit or not self.revision: raise ValueError("incomplete evidence")
        if not math.isfinite(float(self.value)) or self.value<0: raise ValueError("invalid value")
        if self.status!="accepted": raise ValueError("review required")
        return self
def fingerprint(rows):
    data=[r.validate().__dict__ for r in sorted(rows,key=lambda x:x.record_id)]
    return sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()
