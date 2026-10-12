from core.platform.maintenance_lifecycle_v1 import can_transition, require_transition
from core.platform.release_health_v1 import assess_release_health, require_release_health
from core.platform.support_diagnostics_v1 import diagnostics_snapshot, redact_diagnostics


def test_release_health_is_fail_closed_and_order_stable():
    checks = {"smoke": True, "regression": True, "artifacts": True}
    a = require_release_health(checks)
    b = require_release_health(dict(reversed(list(checks.items()))))
    assert a.healthy and a.blockers == () and a.fingerprint == b.fingerprint


def test_release_health_blocks_failed_gate():
    result = assess_release_health({"smoke": True, "regression": False})
    assert not result.healthy and result.blockers == ("regression",)


def test_support_diagnostics_redact_secrets_and_are_stable():
    payload = {"version": "1.0", "token": "do-not-leak", "nested": {"api_key": "secret", "ok": 7}}
    redacted = redact_diagnostics(payload)
    assert redacted["token"] == "<redacted>"
    assert redacted["nested"]["api_key"] == "<redacted>"
    snapshot = diagnostics_snapshot(payload)
    assert "do-not-leak" not in snapshot and "secret" not in snapshot
    assert snapshot == diagnostics_snapshot(dict(reversed(list(payload.items()))))


def test_maintenance_lifecycle_is_explicit():
    assert can_transition("active", "maintenance").allowed
    assert can_transition("retired", "active").allowed is False
    assert require_transition("maintenance", "active").allowed
