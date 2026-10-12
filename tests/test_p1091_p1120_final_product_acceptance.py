from core.platform.final_product_acceptance_v1 import (
    REQUIRED_CHECKS,
    evaluate_final_product_acceptance,
    require_final_product_acceptance,
)

VALID = {name: True for name in REQUIRED_CHECKS}

def test_complete_acceptance_is_valid_and_deterministic():
    a = evaluate_final_product_acceptance(VALID)
    b = evaluate_final_product_acceptance(dict(reversed(list(VALID.items()))))
    assert a.accepted
    assert not a.blockers
    assert a.fingerprint == b.fingerprint

def test_missing_check_fails_closed():
    evidence = dict(VALID)
    evidence.pop("release_health")
    result = evaluate_final_product_acceptance(evidence)
    assert not result.accepted
    assert "missing check: release_health" in result.blockers

def test_unknown_check_fails_closed():
    result = evaluate_final_product_acceptance({**VALID, "extra": True})
    assert not result.accepted
    assert "unknown check: extra" in result.blockers

def test_non_boolean_status_fails_closed():
    result = evaluate_final_product_acceptance({**VALID, "core_functionality": "yes"})
    assert not result.accepted
    assert "core_functionality must be boolean" in result.blockers

def test_failed_check_blocks_acceptance():
    result = evaluate_final_product_acceptance({**VALID, "ui_surfaces": False})
    assert not result.accepted
    assert "ui_surfaces is not accepted" in result.blockers

def test_empty_input_fails_closed():
    result = evaluate_final_product_acceptance({})
    assert not result.accepted
    assert "checks must be a non-empty mapping" in result.blockers

def test_fingerprint_changes_when_evidence_changes():
    a = evaluate_final_product_acceptance(VALID)
    b = evaluate_final_product_acceptance({**VALID, "data_integrity": False})
    assert a.fingerprint != b.fingerprint

def test_require_raises_on_incomplete_acceptance():
    try:
        require_final_product_acceptance({**VALID, "release_health": False})
    except ValueError as exc:
        assert "final product acceptance failed" in str(exc)
    else:
        raise AssertionError("failed acceptance must raise")
