"""Deterministic production bundle contract for takeoff/BOQ/estimate acceptance."""
from __future__ import annotations
import hashlib, json
from typing import Any

def build_acceptance_bundle(*, project_id: str, revision: str, takeoff: Any,
                            boq: Any, estimate: Any, provenance: Any) -> dict:
    if not str(project_id).strip() or not str(revision).strip():
        raise ValueError("project_id and revision are required")
    payload = {"schema":"structuralpro-production-acceptance-1",
               "project_id":str(project_id), "revision":str(revision),
               "takeoff":takeoff, "boq":boq, "estimate":estimate,
               "provenance":provenance}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**payload, "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}

def validate_acceptance_bundle(bundle: dict) -> dict:
    required=("schema","project_id","revision","takeoff","boq","estimate","provenance","fingerprint")
    missing=[k for k in required if k not in bundle]
    if missing: raise ValueError(f"missing acceptance fields: {','.join(missing)}")
    if bundle["schema"]!="structuralpro-production-acceptance-1": raise ValueError("unsupported schema")
    check=dict(bundle); fingerprint=check.pop("fingerprint")
    canonical=json.dumps(check, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if fingerprint!=expected: raise ValueError("acceptance fingerprint mismatch")
    return {"valid":True,"fingerprint":fingerprint}
