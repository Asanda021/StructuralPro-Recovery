from core.platform.release_candidate_v1 import (
    REQUIRED_FIELDS,
    evaluate_release_candidate,
    require_release_candidate,
)

VALID = {
    "version": "0.1.0",
    "commit": "a" * 40,
    "acceptance_fingerprint": "b" * 64,
    "release_health_fingerprint": "c" * 64,
    "production_boundary_fingerprint": "d" * 64,
    "artifacts": {"package.zip": "e" * 64},
}

def test_valid_candidate_is_deterministic():
    a = evaluate_release_candidate(VALID)
    b = evaluate_release_candidate(dict(reversed(list(VALID.items()))))
    assert a.ready and not a.blockers
    assert a.fingerprint == b.fingerprint

def test_missing_field_fails_closed():
    evidence = dict(VALID)
    evidence.pop("commit")
    result = evaluate_release_candidate(evidence)
    assert not result.ready
    assert "missing field: commit" in result.blockers

def test_unknown_field_fails_closed():
    result = evaluate_release_candidate({**VALID, "extra": True})
    assert not result.ready
    assert "unknown field: extra" in result.blockers

def test_invalid_digest_fails_closed():
    result = evaluate_release_candidate({**VALID, "artifacts": {"package.zip": "not-a-digest"}})
    assert not result.ready
    assert "package.zip must be a lowercase SHA-256" in result.blockers

def test_empty_artifacts_fail_closed():
    result = evaluate_release_candidate({**VALID, "artifacts": {}})
    assert not result.ready
    assert "artifacts must be a non-empty mapping" in result.blockers

def test_fingerprint_changes_on_mutation():
    a = evaluate_release_candidate(VALID)
    b = evaluate_release_candidate({**VALID, "version": "0.1.1"})
    assert a.fingerprint != b.fingerprint

def test_require_raises_when_not_ready():
    try:
        require_release_candidate({**VALID, "commit": ""})
    except ValueError as exc:
        assert "release candidate gate failed" in str(exc)
    else:
        raise AssertionError("expected ValueError")
