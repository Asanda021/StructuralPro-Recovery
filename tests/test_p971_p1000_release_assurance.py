import pytest

from core.platform.release_assurance_v1 import assurance_fingerprint, validate_release_manifest

def manifest():
    return {
        "version": "1.0.0",
        "commit": "abc123",
        "artifacts": [
            {"name": "desktop", "sha256": "a" * 64},
            {"name": "docs", "sha256": "b" * 64},
        ],
        "environment": {"python": "3.11", "platform": "linux"},
    }

def test_valid_manifest_is_deterministic():
    a = validate_release_manifest(manifest())
    b = validate_release_manifest({
        "environment": {"platform": "linux", "python": "3.11"},
        "artifacts": [{"sha256": "a"*64, "name": "desktop"}, {"sha256": "b"*64, "name": "docs"}],
        "commit": "abc123", "version": "1.0.0",
    })
    assert a.valid and b.valid
    assert a.fingerprint == b.fingerprint

@pytest.mark.parametrize("field", ["version", "commit", "artifacts", "environment"])
def test_missing_required_field_fails_closed(field):
    payload = manifest()
    del payload[field]
    result = validate_release_manifest(payload)
    assert not result.valid
    assert f"missing:{field}" in result.errors

def test_unknown_field_fails_closed():
    payload = manifest()
    payload["debug"] = True
    assert not validate_release_manifest(payload).valid

def test_bad_artifact_digest_fails_closed():
    payload = manifest()
    payload["artifacts"][0]["sha256"] = "not-a-digest"
    result = validate_release_manifest(payload)
    assert not result.valid
    assert "artifacts[0]:invalid:sha256" in result.errors

def test_duplicate_artifact_name_fails_closed():
    payload = manifest()
    payload["artifacts"][1]["name"] = "desktop"
    assert not validate_release_manifest(payload).valid

def test_environment_is_strict():
    payload = manifest()
    payload["environment"]["extra"] = "x"
    assert not validate_release_manifest(payload).valid

def test_fingerprint_changes_on_manifest_mutation():
    payload = manifest()
    before = assurance_fingerprint(payload)
    payload["version"] = "1.0.1"
    assert before != assurance_fingerprint(payload)

def test_non_object_rejected():
    with pytest.raises(ValueError):
        validate_release_manifest([])
