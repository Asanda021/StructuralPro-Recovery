import pytest
from core.launch.production_launch_readiness_v2 import (
    LaunchGate, ReadinessEvidence, evaluate_launch, fingerprint_evidence,
)

GATES = (
    LaunchGate("engineering_quality"),
    LaunchGate("security"),
    LaunchGate("beta_evidence"),
    LaunchGate("commercial_readiness"),
)

def ev(gate, status="pass", source="test", observed="2026-10-04"):
    return ReadinessEvidence(gate, status, source, observed)

def test_all_required_gates_pass():
    result = evaluate_launch(GATES, [ev(g) for g in ("engineering_quality","security","beta_evidence","commercial_readiness")])
    assert result.decision == "go"
    assert not result.blocking_gates
    assert not result.unknown_gates

def test_missing_required_evidence_is_not_go():
    result = evaluate_launch(GATES, [ev("engineering_quality")])
    assert result.decision == "needs_evidence"
    assert "security" in result.unknown_gates

def test_failed_required_gate_is_no_go():
    evidence = [ev(g) for g in ("engineering_quality","security","beta_evidence","commercial_readiness")]
    evidence[1] = ev("security", "fail")
    result = evaluate_launch(GATES, evidence)
    assert result.decision == "no_go"
    assert result.blocking_gates == ("security",)

def test_unknown_does_not_count_as_pass():
    evidence = [ev(g) for g in ("engineering_quality","security","commercial_readiness")]
    evidence.append(ev("beta_evidence", "unknown"))
    result = evaluate_launch(GATES, evidence)
    assert result.decision == "needs_evidence"

def test_invalid_evidence_fails_closed():
    with pytest.raises(ValueError):
        fingerprint_evidence([ReadinessEvidence("security", "pass", "", "2026-10-04")])
