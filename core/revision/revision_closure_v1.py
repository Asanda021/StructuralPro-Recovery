"""Fail-closed revision impact review and closure contract."""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any
from core.revision.revision_impact_v1 import RevisionImpactReport, impact_totals, validate_change

ALLOWED_STATUSES = ("open", "reviewed", "accepted", "rejected")

def build_revision_closure(report: RevisionImpactReport, reviews: dict[str, str]) -> dict[str, Any]:
    totals = impact_totals(report)
    expected = {c.element_id for c in report.changes}
    if set(reviews) != expected:
        raise ValueError("every impacted element requires an explicit review status")
    if any(status not in ALLOWED_STATUSES for status in reviews.values()):
        raise ValueError("invalid review status")
    for change in report.changes:
        validate_change(change)
    payload = {"schema":"structuralpro-revision-closure-1",
               "project_id":report.project_id,"old_revision":report.old_revision,
               "new_revision":report.new_revision,
               "changes":[asdict(c) for c in report.changes],
               "reviews":{k:reviews[k] for k in sorted(reviews)},
               "totals":totals}
    normalized = _normalize(payload)
    canonical=json.dumps(normalized,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return {**payload,"fingerprint":sha256(canonical.encode("utf-8")).hexdigest()}

def validate_revision_closure(closure: dict[str, Any]) -> dict[str, Any]:
    required=("schema","project_id","old_revision","new_revision","changes","reviews","totals","fingerprint")
    missing=[k for k in required if k not in closure]
    if missing: raise ValueError(f"missing closure fields: {','.join(missing)}")
    if closure["schema"] != "structuralpro-revision-closure-1": raise ValueError("unsupported closure schema")
    expected={c["element_id"] for c in closure["changes"]}
    if set(closure["reviews"]) != expected: raise ValueError("review coverage is incomplete")
    if any(v not in ALLOWED_STATUSES for v in closure["reviews"].values()): raise ValueError("invalid review status")
    check=dict(closure); fp=check.pop("fingerprint")
    canonical=json.dumps(_normalize(check),ensure_ascii=False,sort_keys=True,separators=(",",":"))
    if fp != sha256(canonical.encode("utf-8")).hexdigest(): raise ValueError("closure fingerprint mismatch")
    return {"valid":True,"closed":all(v in ("accepted","rejected") for v in closure["reviews"].values()),"fingerprint":fp}

def _normalize(value: Any) -> Any:
    from decimal import Decimal
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, dict): return {k:_normalize(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [_normalize(v) for v in value]
    return value
