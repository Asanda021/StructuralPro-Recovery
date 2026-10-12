from dataclasses import replace

from core.ai.takeoff_intelligence_v1 import IntelligenceGroup
from core.ai.takeoff_production_v1 import (
    build_production_takeoff,
    validate_production_package,
)


def g(cid="c1", source="G1", confidence=.85):
    return IntelligenceGroup(
        element_type="beam",
        metric="length",
        unit="m",
        quantity=6,
        candidate_ids=(cid,),
        source_ids=(source,),
        confidence=confidence,
    )


def test_p25_valid_package_is_review_only():
    package = build_production_takeoff([g()])
    assert package.status == "review_required"
    assert package.fail_closed is False
    assert package.ready_for_review is True
    assert package.approved is False
    ok, errors = validate_production_package(package)
    assert ok is True
    assert errors == ()


def test_p25_low_confidence_fails_closed():
    package = build_production_takeoff([g(confidence=.69)])
    assert package.status == "blocked"
    assert package.fail_closed is True
    assert package.ready_for_review is False
    assert "confidence below production threshold: beam/length" in package.issues


def test_p25_duplicate_identity_fails_closed():
    package = build_production_takeoff([g("c1", "G1"), g("c1", "G2")])
    assert package.fail_closed is True
    assert "duplicate candidate identity" in package.issues


def test_p25_duplicate_source_across_groups_fails_closed():
    package = build_production_takeoff([g("c1", "G1"), g("c2", "G1")])
    assert package.fail_closed is True
    assert "duplicate source identity across groups" in package.issues


def test_p25_invalid_confirmation_gate_fails_closed():
    package = build_production_takeoff([replace(g(), needs_confirmation=False)])
    assert package.fail_closed is True
    assert "human confirmation gate removed" in package.issues


def test_p25_fingerprint_is_deterministic():
    first = build_production_takeoff([g()])
    second = build_production_takeoff([g()])
    assert first.fingerprint == second.fingerprint


def test_p25_automatic_approval_is_rejected():
    package = build_production_takeoff([g()])
    tampered = replace(package, approved=True)
    ok, errors = validate_production_package(tampered)
    assert ok is False
    assert "automatic approval is forbidden" in errors
