"""Deterministic release-preparation gate for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping

REQUIRED_FIELDS=("version","candidate_fingerprint","release_notes","rollback_plan","provenance")
@dataclass(frozen=True)
class ReleasePreparation:
    ready: bool
    blockers: tuple[str,...]
    fingerprint: str

def evaluate_release_preparation(evidence: Mapping[str,object])->ReleasePreparation:
    errors=[]
    if not isinstance(evidence,Mapping) or not evidence:
        errors.append("evidence must be a non-empty mapping"); canonical={}
    else:
        errors += [f"unknown field: {x}" for x in sorted(set(evidence)-set(REQUIRED_FIELDS))]
        errors += [f"missing field: {x}" for x in sorted(set(REQUIRED_FIELDS)-set(evidence))]
        canonical=dict(evidence)
        for k in REQUIRED_FIELDS:
            if k in evidence and (not isinstance(evidence[k],str) or not evidence[k].strip()):
                errors.append(f"{k} must be a non-empty string")
    fp=sha256(json.dumps(canonical,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
    return ReleasePreparation(not errors,tuple(sorted(set(errors))),fp)

def require_release_preparation(evidence):
    result=evaluate_release_preparation(evidence)
    if not result.ready: raise ValueError("release preparation failed")
    return result
