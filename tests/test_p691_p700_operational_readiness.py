from core.platform.operational_readiness_v1 import assess_operational_readiness, require_operational_readiness

def test_operational_readiness_is_complete_and_stable():
    checks = {"backup_restore": True, "support_docs": True, "audit": True, "recovery": True}
    a = require_operational_readiness(checks)
    b = require_operational_readiness(dict(reversed(list(checks.items()))))
    assert a.ready and a.blockers == () and a.fingerprint == b.fingerprint

def test_operational_failure_blocks_release_path():
    r = assess_operational_readiness({"backup_restore": True, "recovery": False})
    assert not r.ready and r.blockers == ("recovery",)
