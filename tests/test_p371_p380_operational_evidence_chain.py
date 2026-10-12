from core.platform.operational_evidence_v1 import OperationalEvidence
from core.platform.operational_evidence_snapshot_v1 import snapshot_from_evidence
from core.platform.operational_evidence_archive_v1 import archive_from_snapshot
from core.platform.operational_evidence_chain_v1 import (
    chain_from_archives, validate_chain, verify_chain, serialize_chain,
    restore_chain, replay_chain,
)


def archive(version, ident, fp):
    evidence = OperationalEvidence(True, (("runtime", True),), fp * 64, ())
    snap = snapshot_from_evidence(evidence, app_version=version)
    return archive_from_snapshot(snap, archive_id=ident)


def test_chain_is_deterministic_and_verifiable():
    archives = [archive("1.2.3", "run-001", "a"), archive("1.2.3", "run-002", "b")]
    c1 = chain_from_archives(archives)
    c2 = chain_from_archives(archives)
    assert c1 == c2
    assert validate_chain(c1) == []
    assert verify_chain(c1)


def test_roundtrip_preserves_chain():
    chain = chain_from_archives([archive("1.2.3", "run-001", "a")])
    assert restore_chain(serialize_chain(chain)) == chain


def test_archive_change_breaks_chain():
    archives = [archive("1.2.3", "run-001", "a")]
    chain = chain_from_archives(archives)
    changed = archive("1.2.3", "run-001", "b")
    assert not replay_chain(chain, changed and [changed])


def test_order_is_integrity_relevant():
    archives = [archive("1.2.3", "run-001", "a"), archive("1.2.3", "run-002", "b")]
    chain = chain_from_archives(archives)
    assert not replay_chain(chain, list(reversed(archives)))


def test_tampering_is_rejected():
    chain = chain_from_archives([archive("1.2.3", "run-001", "a")])
    tampered = dict(chain)
    tampered["sequence"] = [99]
    assert not verify_chain(tampered)
