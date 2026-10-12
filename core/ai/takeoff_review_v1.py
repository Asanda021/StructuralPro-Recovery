"""P26 AI Takeoff Human Review Gate.

Provides a deterministic, explicit human decision boundary for P25
production takeoff packages. No automatic approval is possible.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .takeoff_production_v1 import ProductionTakeoffPackage, validate_production_package


@dataclass(frozen=True)
class TakeoffReviewDecision:
    package_fingerprint: str
    reviewer_id: str
    decision: str
    reason: str
    decision_fingerprint: str


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(package_fingerprint: str, reviewer_id: str, decision: str, reason: str) -> str:
    payload = {
        "schema": "p26-review-v1",
        "package_fingerprint": package_fingerprint,
        "reviewer_id": reviewer_id,
        "decision": decision,
        "reason": reason,
    }
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def create_review_decision(
    package: ProductionTakeoffPackage,
    *,
    reviewer_id: str,
    approve: bool,
    reason: str,
) -> TakeoffReviewDecision:
    """Create an explicit, traceable human decision for a valid review package."""
    ok, errors = validate_production_package(package)
    if not ok:
        raise ValueError("package is not reviewable: " + "; ".join(errors))
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("reviewer_id is required")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason is required")
    decision = "approved" if approve else "rejected"
    reviewer = reviewer_id.strip()
    rationale = reason.strip()
    return TakeoffReviewDecision(
        package_fingerprint=package.fingerprint,
        reviewer_id=reviewer,
        decision=decision,
        reason=rationale,
        decision_fingerprint=_fingerprint(package.fingerprint, reviewer, decision, rationale),
    )


def validate_review_decision(
    package: ProductionTakeoffPackage,
    decision: TakeoffReviewDecision,
) -> tuple[bool, tuple[str, ...]]:
    """Fail closed if a decision is detached, malformed, or tampered with."""
    errors: list[str] = []
    package_ok, package_errors = validate_production_package(package)
    if not package_ok:
        errors.extend(package_errors)
    if decision.package_fingerprint != package.fingerprint:
        errors.append("decision package fingerprint mismatch")
    if not decision.reviewer_id.strip():
        errors.append("reviewer identity is missing")
    if decision.decision not in {"approved", "rejected"}:
        errors.append("invalid review decision")
    if not decision.reason.strip():
        errors.append("review reason is missing")
    expected = _fingerprint(
        decision.package_fingerprint,
        decision.reviewer_id.strip(),
        decision.decision,
        decision.reason.strip(),
    )
    if decision.decision_fingerprint != expected:
        errors.append("review decision fingerprint mismatch")
    return not errors, tuple(sorted(set(errors)))
