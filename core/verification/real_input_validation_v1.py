from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

SUPPORTED={"pdf","dwg","dxf","ifc","image"}

@dataclass(frozen=True)
class InputEvidence:
    project_id:str
    source_id:str
    kind:str
    sha256:str
    observed_at:str

@dataclass(frozen=True)
class InputValidation:
    source_count:int
    kinds:tuple[str,...]
    decision:str
    fingerprint:str

def validate_inputs(items):
    if not items: raise ValueError("real input evidence required")
    seen=set()
    for x in items:
        if not all((x.project_id.strip(),x.source_id.strip(),x.kind.strip(),x.sha256.strip(),x.observed_at.strip())): raise ValueError("incomplete input evidence")
        if x.kind not in SUPPORTED: raise ValueError("unsupported input kind")
        if len(x.sha256)!=64 or any(c not in "0123456789abcdefABCDEF" for c in x.sha256): raise ValueError("invalid sha256")
        if x.source_id in seen: raise ValueError("duplicate source")
        seen.add(x.source_id)

def assess_inputs(items):
    validate_inputs(items)
    kinds=tuple(sorted({x.kind for x in items}))
    payload="|".join(sorted(f"{x.project_id}|{x.source_id}|{x.kind}|{x.sha256.lower()}|{x.observed_at}" for x in items))
    return InputValidation(len(items),kinds,"go",sha256(payload.encode()).hexdigest())
