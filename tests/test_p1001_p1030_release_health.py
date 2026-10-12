import pytest

from core.platform.release_health_v2 import (
    assess_release_health_v2,
    require_release_health_v2,
)


def test_valid_health_is_deterministic():
    a = assess_release_health_v2({"tests": True, "smoke": True})
    b = assess_release_health_v2({"smoke": True, "tests": True})
    assert a.healthy
    assert not a.blockers
    assert a.fingerprint == b.fingerprint


def test_failed_check_blocks_release():
    result = assess_release_health_v2({"tests": True, "smoke": False})
    assert not result.healthy
    assert result.blockers == ("smoke",)


def test_empty_or_non_mapping_fails_closed():
    assert not assess_release_health_v2({}).healthy
    assert not assess_release_health_v2([]).healthy


def test_non_boolean_status_fails_closed():
    result = assess_release_health_v2({"tests": "success"})
    assert not result.healthy
    assert "tests: status must be boolean" in result.blockers


def test_blank_name_fails_closed():
    result = assess_release_health_v2({" ": True})
    assert not result.healthy


def test_require_raises_on_incomplete_health():
    with pytest.raises(RuntimeError):
        require_release_health_v2({"tests": False})


def test_fingerprint_changes_when_evidence_changes():
    a = assess_release_health_v2({"tests": True})
    b = assess_release_health_v2({"tests": False})
    assert a.fingerprint != b.fingerprint
