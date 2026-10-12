import pytest

from core.platform.production_integrity_v1 import evidence_fingerprint, validate_release_evidence

def valid_payload():
    return {
        "build_id": "build-941",
        "version": "1.0.0",
        "commit": "abc123",
        "checks": [
            {"name": "tests", "status": "success"},
            {"name": "ci", "status": "success"},
        ],
    }

def test_valid_release_evidence_is_deterministic():
    a = validate_release_evidence(valid_payload())
    b = validate_release_evidence({
        "checks": [{"status": "success", "name": "tests"}, {"status": "success", "name": "ci"}],
        "commit": "abc123", "version": "1.0.0", "build_id": "build-941",
    })
    assert a.valid and b.valid
    assert a.fingerprint == b.fingerprint

def test_missing_evidence_fails_closed():
    payload = valid_payload()
    del payload["commit"]
    result = validate_release_evidence(payload)
    assert not result.valid
    assert "missing:commit" in result.errors

def test_unknown_top_level_field_fails_closed():
    payload = valid_payload()
    payload["debug"] = True
    result = validate_release_evidence(payload)
    assert not result.valid
    assert "unknown:debug" in result.errors

def test_non_success_check_fails_closed():
    payload = valid_payload()
    payload["checks"][0]["status"] = "skipped"
    result = validate_release_evidence(payload)
    assert not result.valid
    assert "checks[0]:status_not_success" in result.errors

def test_duplicate_check_names_fail_closed():
    payload = valid_payload()
    payload["checks"][1]["name"] = "tests"
    result = validate_release_evidence(payload)
    assert not result.valid
    assert "checks:duplicate_name" in result.errors

def test_malformed_check_fails_closed():
    payload = valid_payload()
    payload["checks"].append("ci")
    result = validate_release_evidence(payload)
    assert not result.valid
    assert "checks[2]:object_required" in result.errors

def test_mutation_changes_evidence_fingerprint():
    payload = valid_payload()
    before = evidence_fingerprint(payload)
    payload["version"] = "1.0.1"
    assert before != evidence_fingerprint(payload)

def test_non_object_rejected():
    with pytest.raises(ValueError):
        validate_release_evidence([])  # type: ignore[arg-type]
