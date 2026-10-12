from core.platform.post_release_verification_v1 import evaluate_post_release_verification, require_post_release_verification

VALID = {
    "version": "0.1.0",
    "commit": "a" * 40,
    "production_release_fingerprint": "b" * 64,
    "checks": {"smoke": True, "health": True, "artifact_parity": True},
}

def test_valid_and_deterministic():
    a = evaluate_post_release_verification(VALID)
    b = evaluate_post_release_verification(dict(reversed(list(VALID.items()))))
    assert a.verified and not a.blockers and a.fingerprint == b.fingerprint

def test_missing_unknown_and_empty_checks_fail():
    x = dict(VALID); x.pop("commit")
    assert not evaluate_post_release_verification(x).verified
    assert not evaluate_post_release_verification({**VALID, "extra": True}).verified
    assert not evaluate_post_release_verification({**VALID, "checks": {}}).verified

def test_non_boolean_and_failed_check_block():
    assert not evaluate_post_release_verification({**VALID, "checks": {"smoke": "ok"}}).verified
    assert not evaluate_post_release_verification({**VALID, "checks": {"smoke": False}}).verified

def test_fingerprint_changes_on_mutation():
    assert evaluate_post_release_verification(VALID).fingerprint != evaluate_post_release_verification({**VALID, "version": "0.1.1"}).fingerprint

def test_require_raises():
    try:
        require_post_release_verification({**VALID, "commit": ""})
    except ValueError as exc:
        assert "post-release verification failed" in str(exc)
    else:
        raise AssertionError("expected ValueError")
