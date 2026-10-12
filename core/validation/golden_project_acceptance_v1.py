"""Deterministic golden-project acceptance contract for production validation."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any

REQUIRED_SECTIONS = ("quantity", "boq", "estimate", "report", "revision")

def build_golden_project(*, project_id: str, revision: str, sections: dict[str, Any]) -> dict[str, Any]:
    if not project_id.strip() or not revision.strip():
        raise ValueError("project identity is required")
    missing=[k for k in REQUIRED_SECTIONS if k not in sections]
    if missing: raise ValueError("missing golden sections: " + ",".join(missing))
    payload={"schema":"structuralpro-golden-project-1","project_id":project_id,
             "revision":revision,"sections":sections}
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
    return {**payload,"fingerprint":sha256(canonical.encode()).hexdigest()}

def validate_golden_project(golden: dict[str, Any]) -> dict[str, Any]:
    required=("schema","project_id","revision","sections","fingerprint")
    if any(k not in golden for k in required): raise ValueError("golden project is incomplete")
    if golden["schema"] != "structuralpro-golden-project-1": raise ValueError("unsupported golden schema")
    if any(k not in golden["sections"] for k in REQUIRED_SECTIONS): raise ValueError("golden sections incomplete")
    payload={k:golden[k] for k in ("schema","project_id","revision","sections")}
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
    expected=sha256(canonical.encode()).hexdigest()
    if expected != golden["fingerprint"]: raise ValueError("golden fingerprint mismatch")
    return {"valid":True,"project_id":golden["project_id"],"revision":golden["revision"],"fingerprint":expected}
