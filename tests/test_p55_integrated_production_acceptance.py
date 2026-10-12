from core.acceptance.integrated_production_acceptance_v2 import AcceptanceEvidence, accept_production
from core.integration.p48_p52_release_review import IntegrationReview

def _integration(decision="go"):
    return IntegrationReview(decision, None, "go", "s", "b", "c", "integration-fp")

def test_acceptance_is_deterministic_and_accepts_explicit_passes():
    evidence = (
        AcceptanceEvidence("beta", "pass", "verified-record", "2026-10-04"),
        AcceptanceEvidence("security", "pass", "ci", "2026-10-04"),
    )
    first = accept_production(_integration(), evidence)
    second = accept_production(_integration(), evidence)
    assert first.decision == "accepted"
    assert first.fingerprint == second.fingerprint

def test_acceptance_fails_closed_without_evidence():
    try:
        accept_production(_integration(), ())
    except ValueError:
        return
    raise AssertionError("missing evidence must fail closed")

def test_acceptance_does_not_override_integration_needs_evidence():
    evidence = (AcceptanceEvidence("release", "pass", "ci", "2026-10-04"),)
    result = accept_production(_integration("needs_evidence"), evidence)
    assert result.decision == "needs_evidence"
