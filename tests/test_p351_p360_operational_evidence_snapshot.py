from core.platform.operational_evidence_v1 import OperationalEvidence
from core.platform.operational_evidence_snapshot_v1 import (
    replay_matches, restore_snapshot, serialize_snapshot,
    snapshot_from_evidence, validate_snapshot, verify_snapshot,
)

def evidence(ready=True):
    return OperationalEvidence(
        ready=ready,
        checks=(("runtime", ready), ("diagnostics", ready)),
        fingerprint="a" * 64,
        errors=() if ready else ("blocked",),
    )

def test_snapshot_is_deterministic_and_verifiable():
    snap1 = snapshot_from_evidence(evidence(), app_version="1.2.3")
    snap2 = snapshot_from_evidence(evidence(), app_version="1.2.3")
    assert snap1 == snap2
    assert validate_snapshot(snap1) == []
    assert verify_snapshot(snap1)

def test_json_roundtrip_preserves_snapshot():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    assert restore_snapshot(serialize_snapshot(snap)) == snap

def test_tampering_is_rejected():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    tampered = dict(snap)
    tampered["ready"] = False
    assert not verify_snapshot(tampered)
    assert validate_snapshot(tampered) == []

def test_invalid_schema_is_rejected():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    snap["schema_version"] = "v9"
    assert not verify_snapshot(snap)

def test_replay_matches_exact_evidence():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    assert replay_matches(snap, evidence())

def test_replay_detects_changed_evidence():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    changed = OperationalEvidence(
        ready=True,
        checks=(("runtime", True), ("diagnostics", False)),
        fingerprint="b" * 64,
        errors=(),
    )
    assert not replay_matches(snap, changed)
