import pytest

from core.platform.activation_integrity_v1 import (
    ActivationEvidence,
    EntitlementEvidence,
    RevocationPolicy,
    activation_allowed,
    activation_fingerprint,
)


def evidence(result="accepted"):
    return ActivationEvidence(
        "LIC-1",
        "a" * 64,
        "StructuralPro",
        "issuer-1",
        "1.0.0",
        result,
        "offline",
        "2026-10-03",
    )


def entitlements():
    return EntitlementEvidence("LIC-1", ("takeoff", "reports"))


def policy():
    return RevocationPolicy(frozenset(), False)


def test_activation_accepts_matching_non_revoked_evidence():
    assert activation_allowed(evidence(), entitlements(), policy())


def test_rejected_result_fails_closed():
    assert not activation_allowed(evidence("rejected"), entitlements(), policy())


def test_revoked_license_fails_closed():
    revoked = RevocationPolicy(frozenset({"LIC-1"}), True)
    assert not activation_allowed(evidence(), entitlements(), revoked)


def test_license_and_entitlement_identity_must_match():
    with pytest.raises(ValueError):
        EntitlementEvidence("", ("takeoff",)).validate()
    assert not activation_allowed(
        evidence(),
        EntitlementEvidence("LIC-2", ("takeoff",)),
        policy(),
    )


def test_duplicate_entitlements_fail_closed():
    with pytest.raises(ValueError):
        EntitlementEvidence("LIC-1", ("takeoff", "takeoff")).validate()


def test_invalid_activation_evidence_fails_closed():
    with pytest.raises(ValueError):
        ActivationEvidence(
            "LIC-1", "x", "StructuralPro", "issuer-1",
            "1.0.0", "accepted", "offline", "bad-date"
        ).validate()


def test_activation_fingerprint_is_deterministic():
    assert activation_fingerprint(evidence(), entitlements()) == activation_fingerprint(
        evidence(), entitlements()
    )
