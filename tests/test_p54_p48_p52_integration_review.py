from core.beta.real_world_beta_v2 import BetaCase, BetaReview
from core.competitive.competitive_attack_plan_v2 import BenchmarkDimension, CompetitorEvidence
from core.integration.p48_p52_release_review import (
    IntegrationEvidence,
    review_integration,
)
from core.launch.production_launch_readiness_v2 import LaunchGate, ReadinessEvidence
from core.market.continuous_improvement_v2 import (
    FeedbackItem,
    ImprovementCycle,
    ImprovementProposal,
    ReleaseRecord,
)
from core.security_hardening_v2 import AuditEvent, BackupArtifact, SecurityPrincipal


def _inputs():
    evidence = ReadinessEvidence("engineering", "pass", "ci", "2026-10-04")
    return dict(
        principal=SecurityPrincipal("u1", "p1", "owner"),
        project_id="p1",
        backup=BackupArtifact("p1", "b1", "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "2026-10-04"),
        backup_payload=b"hello",
        audit_event=AuditEvent("p1", "u1", "integration-review", "2026-10-04", "ci"),
        beta_cases=(BetaCase("c1", "p1", "beta", 10.0, 10.0, "m3"),),
        beta_reviews=(BetaReview("c1", "reviewer", "accepted", "verified"),),
        competitor_evidence=(CompetitorEvidence("A", "takeoff", "source", "observed", "2026-10-04"),),
        benchmark_dimensions=(BenchmarkDimension("takeoff", 1.0),),
        launch_gates=(LaunchGate("engineering"),),
        evidence=IntegrationEvidence((evidence,), (evidence,), (evidence,), (evidence,)),
        improvement_cycle=ImprovementCycle(
            ReleaseRecord("1.0", "release", "2026-10-04"),
            (),
            (FeedbackItem("f1", "user", "2026-10-04", "reviewed", "accepted"),),
            (ImprovementProposal("p1", "bugfix", ("f1",), "verified", "owner", "approved"),),
            "1.1",
        ),
    )


def test_p48_p52_integration_go_is_deterministic():
    first = review_integration(**_inputs())
    second = review_integration(**_inputs())
    assert first.decision == "go"
    assert first.fingerprint == second.fingerprint
    assert first.security_fingerprint


def test_integration_fails_closed_on_unknown_launch_evidence():
    values = _inputs()
    values["evidence"] = IntegrationEvidence(
        (ReadinessEvidence("engineering", "unknown", "ci", "2026-10-04"),),
        values["evidence"].beta,
        values["evidence"].competitive,
        values["evidence"].launch,
    )
    result = review_integration(**values)
    assert result.decision == "needs_evidence"
