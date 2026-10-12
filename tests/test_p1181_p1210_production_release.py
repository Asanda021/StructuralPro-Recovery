from core.platform.production_release_v1 import evaluate_production_release, require_production_release

VALID = {
    "version": "0.1.0",
    "commit": "a" * 40,
    "release_preparation_fingerprint": "b" * 64,
    "tag": "v0.1.0",
    "deployment": {"environment": "production", "status": "released", "commit": "a" * 40},
}

def test_valid_and_deterministic():
    a = evaluate_production_release(VALID)
    b = evaluate_production_release(dict(reversed(list(VALID.items()))))
    assert a.released and not a.blockers and a.fingerprint == b.fingerprint

def test_missing_unknown_and_bad_status_fail():
    x = dict(VALID); x.pop("tag")
    assert not evaluate_production_release(x).released
    assert not evaluate_production_release({**VALID, "extra": True}).released
    assert not evaluate_production_release({**VALID, "deployment": {**VALID["deployment"], "status": "pending"}}).released

def test_deployment_commit_must_match():
    x = {**VALID, "deployment": {**VALID["deployment"], "commit": "d" * 40}}
    result = evaluate_production_release(x)
    assert not result.released
    assert "deployment.commit must match commit" in result.blockers

def test_fingerprint_changes_on_mutation():
    assert evaluate_production_release(VALID).fingerprint != evaluate_production_release({**VALID, "tag": "v0.1.1"}).fingerprint

def test_require_raises():
    try:
        require_production_release({**VALID, "commit": ""})
    except ValueError as exc:
        assert "production release gate failed" in str(exc)
    else:
        raise AssertionError("expected ValueError")
