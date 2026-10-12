from core.platform.release_acceptance_v1 import evaluate_release_acceptance, require_complete_acceptance

def test_all_release_gates_pass_deterministically():
    checks = {"windows": True, "smoke": True, "reports": True, "backup": True}
    a = require_complete_acceptance(checks)
    b = require_complete_acceptance(dict(reversed(list(checks.items()))))
    assert a.passed and a.blockers == () and a.fingerprint == b.fingerprint

def test_failed_gate_is_fail_closed():
    r = evaluate_release_acceptance({"windows": True, "smoke": False})
    assert not r.passed and r.blockers == ("smoke",)
    try:
        require_complete_acceptance({"windows": True, "smoke": False})
    except ValueError:
        pass
    else:
        raise AssertionError("failed release acceptance must not pass")
