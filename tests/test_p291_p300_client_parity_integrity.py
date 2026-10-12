import pytest
from core.platform.client_parity_integrity_v1 import CapabilityEvidence,validate_parity,parity_fingerprint,command_contract

def rows():
    return [
        CapabilityEvidence("takeoff","windows","implemented","v1"),
        CapabilityEvidence("takeoff","android","contract","v1"),
        CapabilityEvidence("takeoff","telegram","contract","v1"),
        CapabilityEvidence("reports","windows","implemented","v1"),
        CapabilityEvidence("reports","android","contract","v1"),
        CapabilityEvidence("reports","telegram","contract","v1"),
    ]

def test_parity_contract_accepts_one_platform_evidence_each():
    result=validate_parity(rows())
    assert result["valid"] and result["capabilities"]==2 and result["evidence"]==6

def test_duplicate_platform_evidence_fails():
    data=rows()+[CapabilityEvidence("takeoff","windows","implemented","v1")]
    with pytest.raises(ValueError,match="duplicate"):
        validate_parity(data)

def test_contract_version_mismatch_fails():
    data=rows()+[CapabilityEvidence("takeoff","telegram","contract","v2")]
    with pytest.raises(ValueError,match="version"):
        validate_parity(data)

def test_fingerprint_is_order_independent():
    assert parity_fingerprint(rows())==parity_fingerprint(list(reversed(rows())))

def test_command_contract_normalizes_shared_boundary():
    assert command_contract("android","project.open","P1",{"source":"local"})["project_id"]=="P1"

def test_invalid_command_contract_fails_closed():
    with pytest.raises(ValueError):
        command_contract("ios","project.open","P1",{})
    with pytest.raises(ValueError):
        command_contract("android","","P1",{})

def test_payload_must_be_dictionary():
    with pytest.raises(TypeError):
        command_contract("android","project.open","P1",[])
