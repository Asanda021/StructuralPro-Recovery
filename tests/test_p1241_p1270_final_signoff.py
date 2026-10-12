from core.platform.final_signoff_v1 import evaluate_final_signoff, require_final_signoff

VALID = {
    "version": "0.1.0",
    "acceptance_fingerprint": "a" * 64,
    "release_health_fingerprint": "b" * 64,
    "production_boundary_fingerprint": "c" * 64,
    "release_candidate_fingerprint": "d" * 64,
    "release_preparation_fingerprint": "e" * 64,
    "production_release_fingerprint": "f" * 64,
    "post_release_verification_fingerprint": "1" * 64,
    "checks": {
        "acceptance": True,
        "release_health": True,
        "production_boundary": True,
        "release_candidate": True,
        "release_preparation": True,
        "production_release": True,
        "post_release_verification": True,
    },
}

def test_valid_signoff_is_deterministic():
    a = evaluate_final_signoff(VALID)
    b = evaluate_final_signoff(dict(reversed(list(VALID.items()))))
    assert a.signed_off and not a.blockers
    assert a.fingerprint == b.fingerprint

def test_missing_field_fails_closed():
    x = dict(VALID); x.pop("production_release_fingerprint")
    assert not evaluate_final_signoff(x).signed_off

def test_unknown_field_fails_closed():
    result = evaluate_final_signoff({**VALID, "extra": True})
    assert not result.signed_off
    assert "unknown field: extra" in result.blockers

def test_failed_check_blocks():
    x = {**VALID, "checks": {**VALID["checks"], "production_release": False}}
    result = evaluate_final_signoff(x)
    assert not result.signed_off
    assert "production_release is not signed off" in result.blockers

def test_non_boolean_check_blocks():
    result = evaluate_final_signoff({**VALID, "checks": {"release": "yes"}})
    assert not result.signed_off

def test_fingerprint_changes_on_mutation():
    assert evaluate_final_signoff(VALID).fingerprint != evaluate_final_signoff({**VALID, "version": "0.1.1"}).fingerprint

def test_require_raises():
    try:
        require_final_signoff({**VALID, "checks": {}})
    except ValueError as exc:
        assert "final sign-off failed" in str(exc)
    else:
        raise AssertionError("expected ValueError")
