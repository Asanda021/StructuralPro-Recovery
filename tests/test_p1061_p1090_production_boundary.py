from core.platform.production_boundary_validation_v1 import validate_production_boundary, require_production_boundary

VALID = {
    "version": "1.0.0",
    "commit": "abc123",
    "runtime": "python-3.11",
    "dependencies": {"database": True, "storage": True},
    "services": {"api": True, "worker": True},
    "configuration": {"secrets": True, "logging": True},
}

def test_valid_boundary_is_deterministic():
    a = validate_production_boundary(VALID)
    b = validate_production_boundary({**VALID, "services": {"worker": True, "api": True}})
    assert a.valid and not a.errors
    assert a.fingerprint == b.fingerprint

def test_missing_identity_fails_closed():
    r = validate_production_boundary({**VALID, "version": "", "commit": ""})
    assert not r.valid
    assert "version is required" in r.errors
    assert "commit is required" in r.errors

def test_unknown_and_missing_fields_fail_closed():
    r = validate_production_boundary({"version": "1", "commit": "x", "runtime": "py", "unexpected": True})
    assert not r.valid
    assert "unknown field: unexpected" in r.errors
    assert any(e.startswith("missing field:") for e in r.errors)

def test_failed_boundary_item_blocks():
    evidence = {**VALID, "services": {"api": False, "worker": True}}
    r = validate_production_boundary(evidence)
    assert not r.valid
    assert "services.api is not ready" in r.errors

def test_non_boolean_boundary_item_fails_closed():
    evidence = {**VALID, "dependencies": {"database": "ok"}}
    r = validate_production_boundary(evidence)
    assert not r.valid
    assert "dependencies.database must be boolean" in r.errors

def test_empty_section_fails_closed():
    evidence = {**VALID, "configuration": {}}
    r = validate_production_boundary(evidence)
    assert not r.valid
    assert "configuration must be a non-empty mapping" in r.errors

def test_fingerprint_changes_when_evidence_changes():
    a = validate_production_boundary(VALID)
    b = validate_production_boundary({**VALID, "runtime": "python-3.12"})
    assert a.fingerprint != b.fingerprint

def test_require_raises_on_invalid_boundary():
    try:
        require_production_boundary({**VALID, "services": {"api": False}})
    except ValueError as exc:
        assert "production boundary validation failed" in str(exc)
    else:
        raise AssertionError("invalid boundary must raise")
