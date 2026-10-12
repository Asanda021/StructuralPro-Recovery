from core.platform.release_health_attestation_v1 import attest_release_health

def test_valid_attestation_is_deterministic():
    a=attest_release_health("1.0.0","abc123",{"tests":True,"smoke":True})
    b=attest_release_health("1.0.0","abc123",{"smoke":True,"tests":True})
    assert a.valid and not a.errors
    assert a.fingerprint==b.fingerprint

def test_missing_identity_fails_closed():
    r=attest_release_health("","",{"tests":True})
    assert not r.valid
    assert "version is required" in r.errors
    assert "commit is required" in r.errors

def test_failed_health_blocks_attestation():
    r=attest_release_health("1.0.0","abc123",{"tests":False})
    assert not r.valid
    assert "tests" in r.errors

def test_malformed_health_blocks_attestation():
    r=attest_release_health("1.0.0","abc123",{"tests":"success"})
    assert not r.valid

def test_attestation_changes_when_identity_changes():
    a=attest_release_health("1.0.0","abc123",{"tests":True})
    b=attest_release_health("1.0.1","abc123",{"tests":True})
    assert a.fingerprint!=b.fingerprint
