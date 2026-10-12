"""P25 AI Takeoff Production Hardening.

Adds a deterministic production boundary around P23/P24 proposal data.
It validates traceability and confidence, preserves human approval gates,
and emits a stable review package. It never invents or auto-accepts quantities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Iterable

from .takeoff_intelligence_v1 import IntelligenceGroup, intelligence_fingerprint, validate_intelligence


@dataclass(frozen=True)
class ProductionTakeoffPackage:
    status: str
    fail_closed: bool
    ready_for_review: bool
    approved: bool
    minimum_confidence: float
    group_count: int
    groups: tuple[dict, ...]
    fingerprint: str
    issues: tuple[str, ...]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _package_fingerprint(
    groups: tuple[dict, ...], minimum_confidence: float, issues: tuple[str, ...]
) -> str:
    payload = {
        "groups": groups,
        "minimum_confidence": minimum_confidence,
        "issues": issues,
        "schema": "p25-production-v1",
    }
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def build_production_takeoff(
    groups: Iterable[IntelligenceGroup],
    *,
    minimum_confidence: float = 0.70,
) -> ProductionTakeoffPackage:
    """Build a deterministic, review-only production package.

    Invalid evidence or confidence below the policy threshold fails closed.
    Even a fully valid package remains unapproved until a human accepts it.
    """
    if not math.isfinite(minimum_confidence) or not 0 <= minimum_confidence <= 1:
        raise ValueError("minimum_confidence must be between 0 and 1")

    rows = tuple(asdict(group) for group in groups)
    materialized = tuple(
        IntelligenceGroup(**row) if not isinstance(row, IntelligenceGroup) else row
        for row in rows
    )
    valid, validation_errors = validate_intelligence(materialized)
    issues = list(validation_errors)

    candidate_ids = [cid for group in materialized for cid in group.candidate_ids]
    source_ids = [sid for group in materialized for sid in group.source_ids]
    if len(candidate_ids) != len(set(candidate_ids)):
        issues.append("duplicate candidate identity")
    if len(source_ids) != len(set(source_ids)):
        issues.append("duplicate source identity across groups")

    for group in materialized:
        if group.confidence < minimum_confidence:
            issues.append(
                f"confidence below production threshold: {group.element_type}/{group.metric}"
            )

    issues = tuple(sorted(set(issues)))
    fail_closed = bool(issues) or not valid
    status = "blocked" if fail_closed else "review_required"
    fingerprint = _package_fingerprint(rows, minimum_confidence, issues)

    return ProductionTakeoffPackage(
        status=status,
        fail_closed=fail_closed,
        ready_for_review=not fail_closed,
        approved=False,
        minimum_confidence=minimum_confidence,
        group_count=len(materialized),
        groups=rows,
        fingerprint=fingerprint,
        issues=issues,
    )


def validate_production_package(package: ProductionTakeoffPackage) -> tuple[bool, tuple[str, ...]]:
    """Final structural gate before a package can enter a human review UI."""
    errors = list(package.issues)
    if package.approved:
        errors.append("automatic approval is forbidden")
    if package.fail_closed != bool(errors):
        errors.append("fail_closed state is inconsistent")
    if package.ready_for_review != (not bool(errors)):
        errors.append("review readiness state is inconsistent")
    if package.status not in {"blocked", "review_required"}:
        errors.append("invalid production status")
    if package.group_count != len(package.groups):
        errors.append("group count mismatch")
    return not errors, tuple(sorted(set(errors)))
