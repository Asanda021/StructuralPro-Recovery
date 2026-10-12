from dataclasses import replace

from core.ai.takeoff_production_v1 import build_production_takeoff
from core.ai.takeoff_review_v1 import create_review_decision
from core.ai.takeoff_intelligence_v1 import IntelligenceGroup
from core.ai.takeoff_review_audit_v1 import create_audit_entry, validate_audit_chain


def decision():
    group = IntelligenceGroup(
        element_type="beam", metric="length", unit="m", quantity=6,
        candidate_ids=("c1",), source_ids=("G1",), confidence=.85,
    )
    package = build_production_takeoff([group])
    return create_review_decision(package, reviewer_id="engineer-1", approve=True, reason="Checked.")


def test_p27_single_entry_valid():
    entry = create_audit_entry(decision(), sequence=1)
    assert validate_audit_chain((entry,)) == (True, ())


def test_p27_chain_is_linked():
    d = decision()
    a = create_audit_entry(d, sequence=1)
    b = create_audit_entry(d, sequence=2, previous_entry_fingerprint=a.entry_fingerprint)
    assert validate_audit_chain((a, b)) == (True, ())


def test_p27_tampering_fails_closed():
    a = create_audit_entry(decision(), sequence=1)
    tampered = replace(a, reason="changed")
    ok, errors = validate_audit_chain((tampered,))
    assert ok is False
    assert "audit entry fingerprint mismatch" in errors


def test_p27_wrong_chain_link_fails_closed():
    d = decision()
    a = create_audit_entry(d, sequence=1)
    b = create_audit_entry(d, sequence=2, previous_entry_fingerprint="0" * 64)
    ok, errors = validate_audit_chain((a, b))
    assert ok is False
    assert "audit chain link mismatch" in errors


def test_p27_sequence_gap_fails_closed():
    a = create_audit_entry(decision(), sequence=2)
    ok, errors = validate_audit_chain((a,))
    assert ok is False
    assert "audit sequence is not contiguous" in errors


def test_p27_deterministic_entry():
    d = decision()
    a = create_audit_entry(d, sequence=1)
    b = create_audit_entry(d, sequence=1)
    assert a.entry_fingerprint == b.entry_fingerprint
