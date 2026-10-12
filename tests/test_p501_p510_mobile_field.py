import pytest
from core.mobile.mobile_field_v1 import FieldPacket, enqueue, fingerprint, mark_synced


def packet(status="queued", sources=("drawing:A1",)):
    return FieldPacket("p1", "project-1", "device-1", "r1", sources, "payload-hash", status)


def test_enqueue_is_evidence_bound():
    assert enqueue(packet()).source_ids == ("drawing:A1",)


def test_missing_evidence_fails_closed():
    with pytest.raises(ValueError):
        enqueue(packet(sources=()))


def test_conflict_cannot_sync():
    with pytest.raises(ValueError):
        mark_synced(packet("conflict"))


def test_queue_can_sync():
    assert mark_synced(packet()).status == "synced"


def test_fingerprint_deterministic():
    assert fingerprint(packet()) == fingerprint(packet())
