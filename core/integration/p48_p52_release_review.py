"""P54 — Cross-phase integration contract for P48–P52.

Composes the independent security, beta, competitive, launch, and continuous-
improvement contracts without fabricating operational evidence. The integration
layer only accepts evidence explicitly supplied by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Literal

from core.beta.real_world_beta_v2 import BetaCase, BetaReview, beta_fingerprint
from core.competitive.competitive_attack_plan_v2 import (
    BenchmarkDimension,
    CompetitorEvidence,
    plan_fingerprint,
)
from core.launch.production_launch_readiness_v2 import (
    LaunchDecision,
    LaunchGate,
    ReadinessEvidence,
    evaluate_launch,
)
from core.market.continuous_improvement_v2 import ImprovementCycle, evaluate_cycle
from core.security_hardening_v2 import (
    AuditEvent,
    BackupArtifact,
    SecurityPrincipal,
    authorize,
    recovery_fingerprint,
    validate_audit_event,
    validate_backup,
)


@dataclass(frozen=True)
class IntegrationEvidence:
    security: tuple[ReadinessEvidence, ...]
    beta: tuple[ReadinessEvidence, ...]
    competitive: tuple[ReadinessEvidence, ...]
    launch: tuple[ReadinessEvidence, ...]


@dataclass(frozen=True)
class IntegrationReview:
    decision: Literal["go", "no_go", "needs_evidence"]
    launch: LaunchDecision
    improvement_decision: str
    security_fingerprint: str
    beta_fingerprint: str
    competitive_fingerprint: str
    fingerprint: str


def _required_status(evidence: Iterable[ReadinessEvidence]) -> bool:
    rows = tuple(evidence)
    return bool(rows) and all(item.status == "pass" for item in rows)


def review_integration(
    *,
    principal: SecurityPrincipal,
    project_id: str,
    backup: BackupArtifact,
    backup_payload: bytes,
    audit_event: AuditEvent,
    beta_cases: tuple[BetaCase, ...],
    beta_reviews: tuple[BetaReview, ...],
    competitor_evidence: tuple[CompetitorEvidence, ...],
    benchmark_dimensions: tuple[BenchmarkDimension, ...],
    launch_gates: tuple[LaunchGate, ...],
    evidence: IntegrationEvidence,
    improvement_cycle: ImprovementCycle,
) -> IntegrationReview:
    if not authorize(principal, project_id, ("owner", "admin")):
        raise ValueError("integration review requires owner/admin authorization")
    validate_backup(backup, backup_payload)
    validate_audit_event(audit_event)

    security_fp = recovery_fingerprint(project_id, (backup,), "integration-review")
    beta_fp = beta_fingerprint(beta_cases, beta_reviews)
    competitive_fp = plan_fingerprint(competitor_evidence, benchmark_dimensions)

    launch_evidence = (
        evidence.security
        + evidence.beta
        + evidence.competitive
        + evidence.launch
    )
    launch = evaluate_launch(launch_gates, launch_evidence)
    improvement = evaluate_cycle(improvement_cycle)

    if launch.decision == "no_go" or improvement == "no_go":
        decision = "no_go"
    elif launch.decision == "needs_evidence" or improvement == "needs_evidence":
        decision = "needs_evidence"
    elif not _required_status(launch_evidence):
        decision = "needs_evidence"
    else:
        decision = "go"

    payload = {
        "decision": decision,
        "launch": launch.fingerprint,
        "improvement": improvement,
        "security": security_fp,
        "beta": beta_fp,
        "competitive": competitive_fp,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    fingerprint = sha256(raw.encode()).hexdigest()
    return IntegrationReview(
        decision,
        launch,
        improvement,
        security_fp,
        beta_fp,
        competitive_fp,
        fingerprint,
    )
