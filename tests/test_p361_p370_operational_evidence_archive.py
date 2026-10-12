from core.platform.operational_evidence_snapshot_v1 import snapshot_from_evidence
from core.platform.operational_evidence_v1 import OperationalEvidence
from core.platform.operational_evidence_archive_v1 import (
    archive_from_snapshot, restore_archive, serialize_archive,
    validate_archive, verify_archive, retention_key, replay_archive,
)


def evidence(fingerprint="a"):
    return OperationalEvidence(
        ready=True,
        checks=(("runtime", True), ("diagnostics", True)),
        fingerprint=fingerprint * 64,
        errors=(),
    )


def test_archive_is_deterministic_and_integrity_protected():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    a1 = archive_from_snapshot(snap, archive_id="run-001")
    a2 = archive_from_snapshot(snap, archive_id="run-001")
    assert a1 == a2
    assert validate_archive(a1) == []
    assert verify_archive(a1)


def test_json_roundtrip_preserves_archive():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    archive = archive_from_snapshot(snap, archive_id="run-001")
    assert restore_archive(serialize_archive(archive)) == archive


def test_archive_tampering_fails_closed():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    archive = archive_from_snapshot(snap, archive_id="run-001")
    tampered = dict(archive)
    tampered["archive_id"] = "run-999"
    assert not verify_archive(tampered)
    assert "archive integrity verification failed" not in validate_archive(tampered)


def test_nested_snapshot_tampering_is_rejected():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    archive = archive_from_snapshot(snap, archive_id="run-001")
    nested = dict(archive["snapshot"])
    nested["ready"] = False
    tampered = dict(archive)
    tampered["snapshot"] = nested
    assert not verify_archive(tampered)
    assert validate_archive(tampered)


def test_retention_key_is_stable():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    archive = archive_from_snapshot(snap, archive_id="run-001")
    assert retention_key(archive) == ("1.2.3", "run-001")


def test_exact_replay_of_archived_snapshot():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    archive = archive_from_snapshot(snap, archive_id="run-001")
    assert replay_archive(archive, snap)


def test_changed_snapshot_does_not_replay():
    snap = snapshot_from_evidence(evidence(), app_version="1.2.3")
    archive = archive_from_snapshot(snap, archive_id="run-001")
    changed = snapshot_from_evidence(evidence("b"), app_version="1.2.3")
    assert not replay_archive(archive, changed)
