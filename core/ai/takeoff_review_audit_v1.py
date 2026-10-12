"""P27 AI Takeoff review audit trail.

Deterministic, append-only-style audit records for explicit P26 review
decisions. This module records provenance; it never changes quantities
or grants approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .takeoff_review_v1 import TakeoffReviewDecision


@dataclass(frozen=True)
class ReviewAuditEntry:
    sequence: int
    package_fingerprint: str
    decision_fingerprint: str
    reviewer_id: str
    decision: str
    reason: str
    previous_entry_fingerprint: str | None
    entry_fingerprint: str


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _entry_fingerprint(
    sequence: int,
    package_fingerprint: str,
    decision_fingerprint: str,
    reviewer_id: str,
    decision: str,
    reason: str,
    previous_entry_fingerprint: str | None,
) -> str:
    payload = {
        "schema": "p27-review-audit-v1",
        "sequence": sequence,
        "package_fingerprint": package_fingerprint,
        "decision_fingerprint": decision_fingerprint,
        "reviewer_id": reviewer_id,
        "decision": decision,
        "reason": reason,
        "previous_entry_fingerprint": previous_entry_fingerprint,
    }
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()


def create_audit_entry(
    decision: TakeoffReviewDecision,
    *,
    sequence: int,
    previous_entry_fingerprint: str | None = None,
) -> ReviewAuditEntry:
    if not isinstance(sequence, int) or sequence < 1:
        raise ValueError("sequence must be a positive integer")
    if not decision.package_fingerprint or not decision.decision_fingerprint:
        raise ValueError("decision fingerprints are required")
    if not decision.reviewer_id.strip() or not decision.reason.strip():
        raise ValueError("reviewer identity and reason are required")
    if decision.decision not in {"approved", "rejected"}:
        raise ValueError("invalid review decision")
    previous = previous_entry_fingerprint.strip() if previous_entry_fingerprint else None
    entry_fp = _entry_fingerprint(
        sequence,
        decision.package_fingerprint,
        decision.decision_fingerprint,
        decision.reviewer_id.strip(),
        decision.decision,
        decision.reason.strip(),
        previous,
    )
    return ReviewAuditEntry(
        sequence=sequence,
        package_fingerprint=decision.package_fingerprint,
        decision_fingerprint=decision.decision_fingerprint,
        reviewer_id=decision.reviewer_id.strip(),
        decision=decision.decision,
        reason=decision.reason.strip(),
        previous_entry_fingerprint=previous,
        entry_fingerprint=entry_fp,
    )


def validate_audit_chain(entries: tuple[ReviewAuditEntry, ...]) -> tuple[bool, tuple[str, ...]]:
    errors: list[str] = []
    expected_previous = None
    expected_sequence = 1
    for entry in entries:
        if entry.sequence != expected_sequence:
            errors.append("audit sequence is not contiguous")
        if entry.previous_entry_fingerprint != expected_previous:
            errors.append("audit chain link mismatch")
        expected = _entry_fingerprint(
            entry.sequence,
            entry.package_fingerprint,
            entry.decision_fingerprint,
            entry.reviewer_id.strip(),
            entry.decision,
            entry.reason.strip(),
            entry.previous_entry_fingerprint,
        )
        if entry.entry_fingerprint != expected:
            errors.append("audit entry fingerprint mismatch")
        expected_previous = entry.entry_fingerprint
        expected_sequence += 1
    return not errors, tuple(sorted(set(errors)))
