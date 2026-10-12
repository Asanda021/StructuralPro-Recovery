from core.platform.update_release_trust_v1 import (
    build_release_manifest, validate_release_manifest, release_trust_ready, manifest_digest
)

def test_build_and_verify_release_manifest():
    data=b"StructuralPro release"
    m=build_release_manifest("2.0.0","stable",data,{"platform":"windows"})
    assert validate_release_manifest("1.9.0",m,artifact=data)==[]
    assert release_trust_ready("1.9.0",m,artifact=data)
    assert len(manifest_digest(m))==64

def test_tampered_artifact_fails_closed():
    m=build_release_manifest("2.0.0","stable",b"good")
    assert "artifact bytes do not match manifest" in validate_release_manifest("1.0.0",m,artifact=b"bad")

def test_tampered_manifest_fails_closed():
    m=build_release_manifest("2.0.0","stable",b"good")
    m["metadata"]["platform"]="tampered"
    assert "manifest integrity mismatch" in validate_release_manifest("1.0.0",m,artifact=b"good")

def test_downgrade_and_channel_mismatch_fail():
    m=build_release_manifest("1.0.0","beta",b"x")
    channel_errors=validate_release_manifest("0.9.0",m,channel="stable",artifact=b"x")
    assert "channel mismatch" in channel_errors
    version_errors=validate_release_manifest("1.0.0",m,channel="beta",artifact=b"x")
    assert "downgrade or same-version update rejected" in version_errors

def test_missing_required_manifest_fields_fail():
    assert validate_release_manifest("1.0.0",{}) 
