import pytest
from core.sync.offline_sync_contract_v1 import SyncEnvelope, decide_sync

def env(base="r1"):
    return SyncEnvelope("op1","p1",base,"c1",{"change":"explicit"})

def test_matching_revision_is_accepted():
    assert decide_sync(env(), server_revision="r1").status == "accepted"

def test_revision_conflict_is_not_auto_merged():
    d = decide_sync(env(), server_revision="r2")
    assert d.status == "conflict"
    assert "must not be overwritten" in d.reason

def test_identity_is_required():
    with pytest.raises(ValueError):
        SyncEnvelope("","p1","r1","c1",{}).validate()

def test_deterministic_fingerprint():
    assert env().fingerprint() == env().fingerprint()
