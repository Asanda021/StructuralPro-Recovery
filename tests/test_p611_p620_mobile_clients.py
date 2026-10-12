import pytest
from core.clients.mobile_telegram_contract_v1 import ClientEnvelope, ClientCapabilities, accept_envelope

def test_envelope_is_deterministic():
    e = ClientEnvelope("r1","p1","rev1","android","takeoff",{"element":"B1"},("src-1",))
    assert e.fingerprint() == ClientEnvelope("r1","p1","rev1","android","takeoff",{"element":"B1"},("src-1",)).fingerprint()

def test_missing_identity_fails_closed():
    with pytest.raises(ValueError):
        ClientEnvelope("","p1","rev1","telegram","query",{}).validate()

def test_capability_contract():
    c = ClientCapabilities("1.0","1",True,True,True,5_000_000)
    c.validate()

def test_unsupported_protocol_fails():
    e = ClientEnvelope("r","p","v","telegram","query",{})
    with pytest.raises(ValueError):
        accept_envelope(e, supported_protocol="2")

def test_evidence_refs_cannot_be_blank():
    with pytest.raises(ValueError):
        ClientEnvelope("r","p","v","android","query",{},(" ",)).validate()
