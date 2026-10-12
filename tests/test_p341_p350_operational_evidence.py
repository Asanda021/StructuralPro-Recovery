from __future__ import annotations

from core.platform.diagnostics import DiagnosticEvent, build_support_bundle
from core.platform.diagnostics_audit_bridge_v1 import bridge_events
from core.platform.production_readiness_attestation_v1 import (
    ReadinessAttestation,
)
from core.platform.diagnostics_integrity_v1 import build_bundle
from core.platform.operational_evidence_v1 import attest_operational_evidence


def _ready_attestation() -> ReadinessAttestation:
    return ReadinessAttestation(
        True, (("release", True),), "a" * 64, ()
    )


def _bundle() -> dict:
    return build_bundle([], "1.0.0", {"platform": "test"})


def _audit() -> list[dict]:
    return bridge_events(
        [DiagnosticEvent("BOOT_OK", "info", "booted", "runtime", {})]
    )


def test_complete_operational_evidence_is_ready_and_deterministic():
    kwargs = dict(
        app_version="1.0.0",
        readiness=_ready_attestation(),
        runtime_audit={"valid": True, "module_count": 10, "failures": []},
        diagnostics_bundle=_bundle(),
        audit_events=_audit(),
    )
    first = attest_operational_evidence(**kwargs)
    second = attest_operational_evidence(**kwargs)
    assert first.ready
    assert not first.errors
    assert first.fingerprint == second.fingerprint


def test_unready_readiness_blocks_operational_evidence():
    result = attest_operational_evidence(
        app_version="1.0.0",
        readiness=ReadinessAttestation(
            False, (("release", False),), "b" * 64, ("release failed",)
        ),
        runtime_audit={"valid": True},
        diagnostics_bundle=_bundle(),
        audit_events=_audit(),
    )
    assert not result.ready
    assert "readiness: release failed" in result.errors


def test_runtime_failure_blocks_operational_evidence():
    result = attest_operational_evidence(
        app_version="1.0.0",
        readiness=_ready_attestation(),
        runtime_audit={"valid": False, "failures": [{"module": "x"}]},
        diagnostics_bundle=_bundle(),
        audit_events=_audit(),
    )
    assert not result.ready
    assert "runtime audit is not valid" in result.errors


def test_tampered_diagnostics_blocks_operational_evidence():
    bundle = _bundle()
    bundle["app_version"] = "9.9.9"
    result = attest_operational_evidence(
        app_version="1.0.0",
        readiness=_ready_attestation(),
        runtime_audit={"valid": True},
        diagnostics_bundle=bundle,
        audit_events=_audit(),
    )
    assert not result.ready
    assert "application version does not match diagnostics bundle" in result.errors


def test_tampered_audit_chain_blocks_operational_evidence():
    audit = _audit()
    audit[0] = dict(audit[0], message="tampered")
    result = attest_operational_evidence(
        app_version="1.0.0",
        readiness=_ready_attestation(),
        runtime_audit={"valid": True},
        diagnostics_bundle=_bundle(),
        audit_events=audit,
    )
    assert not result.ready
    assert "audit chain integrity verification failed" in result.errors
