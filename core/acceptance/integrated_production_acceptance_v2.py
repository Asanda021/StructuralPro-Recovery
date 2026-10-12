"""P55 — Integrated production acceptance gate.

Evidence-first acceptance on top of the P54 cross-phase integration review.
No operational result is inferred when evidence is absent.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal
from core.integration.p48_p52_release_review import IntegrationReview

@dataclass(frozen=True)
class AcceptanceEvidence:
    gate: str
    status: Literal["pass", "fail", "needs_evidence"]
    source: str
    observed_at: str

@dataclass(frozen=True)
class ProductionAcceptance:
    decision: Literal["accepted", "rejected", "needs_evidence"]
    evidence_count: int
    fingerprint: str

def _validate(row: AcceptanceEvidence) -> None:
    if not all((row.gate.strip(), row.source.strip(), row.observed_at.strip())):
        raise ValueError("incomplete acceptance evidence")
    if row.status not in {"pass", "fail", "needs_evidence"}:
        raise ValueError("invalid acceptance status")

def accept_production(integration: IntegrationReview, evidence: tuple[AcceptanceEvidence, ...]) -> ProductionAcceptance:
    if not evidence:
        raise ValueError("production acceptance requires explicit evidence")
    for row in evidence:
        _validate(row)
    statuses = {row.status for row in evidence}
    if integration.decision == "no_go" or "fail" in statuses:
        decision = "rejected"
    elif integration.decision == "needs_evidence" or "needs_evidence" in statuses:
        decision = "needs_evidence"
    else:
        decision = "accepted"
    material = "|".join(f"{row.gate}:{row.status}:{row.source}:{row.observed_at}" for row in sorted(evidence, key=lambda x: (x.gate, x.source, x.observed_at)))
    fingerprint = sha256(f"{integration.fingerprint}|{decision}|{material}".encode()).hexdigest()
    return ProductionAcceptance(decision, len(evidence), fingerprint)
