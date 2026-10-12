"""Deterministic drawing measurement evidence gate."""
from dataclasses import dataclass
import hashlib,json,math
@dataclass(frozen=True)
class MeasurementEvidence:
 source_id:str; primitive_type:str; value:float; unit:str; formula:str; scale_evidence:str
 def validate(self):
  v=float(self.value)
  if not all(str(x).strip() for x in (self.source_id,self.primitive_type,self.unit,self.formula,self.scale_evidence)): raise ValueError("measurement evidence is incomplete")
  if not math.isfinite(v) or v<0: raise ValueError("measurement must be finite and non-negative")
  return self
def accept_measurements(rows):
 out=[]; seen=set()
 for r in rows:
  e=r.validate(); key=(e.source_id,e.primitive_type,e.formula)
  if key in seen: raise ValueError("duplicate measurement evidence")
  seen.add(key); out.append(e)
 return tuple(out)
def fingerprint(rows):
 return hashlib.sha256(json.dumps([x.__dict__ for x in accept_measurements(rows)],sort_keys=True,separators=(",",":")).encode()).hexdigest()