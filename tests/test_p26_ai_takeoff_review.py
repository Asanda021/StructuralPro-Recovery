from dataclasses import replace

import pytest

from core.ai.takeoff_intelligence_v1 import IntelligenceGroup
from core.ai.takeoff_production_v1 import build_production_takeoff
from core.ai.takeoff_review_v1 import create_review_decision, validate_review_decision


def package():
    group = IntelligenceGroup(
        element_type="beam",
        metric="length",
        unit="m",
        quantity=6,
        candidate_ids=("c1",),
        source_ids=("G1",),
        confidence=.85,
    )
    return build_production_takeoff([group])


def test_p26_explicit_human_approval_is_valid():
    p = package()
    d = create_review_decision(p, reviewer_id="engineer-1", approve=True, reason="Checked drawing evidence.")
    ok, errors = validate_review_decision(p, d)
    assert ok is True
    assert errors == ()
    assert d.decision == "approved"


def test_p26_explicit_rejection_is_valid():
    p = package()
    d = create_review_decision(p, reviewer_id="engineer-1", approve=False, reason="Source drawing is ambiguous.")
    ok, errors = validate_review_decision(p, d)
    assert ok is True
    assert d.decision == "rejected"


def test_p26_missing_reviewer_fails_closed():
    with pytest.raises(ValueError, match="reviewer_id"):
        create_review_decision(package(), reviewer_id=" ", approve=True, reason="Checked.")


def test_p26_missing_reason_fails_closed():
    with pytest.raises(ValueError, match="reason"):
        create_review_decision(package(), reviewer_id="engineer-1", approve=True, reason=" ")


def test_p26_package_binding_fails_closed():
    p = package()
    d = create_review_decision(p, reviewer_id="engineer-1", approve=True, reason="Checked.")
    tampered = replace(d, package_fingerprint="0" * 64)
    ok, errors = validate_review_decision(p, tampered)
    assert ok is False
    assert "decision package fingerprint mismatch" in errors


def test_p26_decision_tampering_fails_closed():
    p = package()
    d = create_review_decision(p, reviewer_id="engineer-1", approve=True, reason="Checked.")
    tampered = replace(d, reason="Changed after approval.")
    ok, errors = validate_review_decision(p, tampered)
    assert ok is False
    assert "review decision fingerprint mismatch" in errors


def test_p26_blocked_package_cannot_be_approved():
    group = IntelligenceGroup(
        element_type="beam",
        metric="length",
        unit="m",
        quantity=6,
        candidate_ids=("c1",),
        source_ids=("G1",),
        confidence=.60,
    )
    p = build_production_takeoff([group])
    with pytest.raises(ValueError, match="not reviewable"):
        create_review_decision(p, reviewer_id="engineer-1", approve=True, reason="Checked.")


def test_p26_decision_fingerprint_is_deterministic():
    p = package()
    a = create_review_decision(p, reviewer_id="engineer-1", approve=True, reason="Checked.")
    b = create_review_decision(p, reviewer_id="engineer-1", approve=True, reason="Checked.")
    assert a.decision_fingerprint == b.decision_fingerprint
