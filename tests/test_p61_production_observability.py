from core.ops.production_observability_v1 import OperationalSignal, assess, validate_signals
def s(status="healthy"): return OperationalSignal("structuralpro","production","health","status", "monitoring", "2026-10-04T00:00:00Z").__class__("structuralpro","production","health",status,"monitoring","2026-10-04T00:00:00Z")
def test_healthy_go():
    assert assess((s(),)).decision=="go"
def test_failed_no_go():
    assert assess((s("failed"),)).decision=="no_go"
def test_degraded_needs_evidence():
    assert assess((s("degraded"),)).decision=="needs_evidence"
def test_unknown_needs_evidence():
    assert assess((s("unknown"),)).decision=="needs_evidence"
def test_empty_fails_closed():
    try: validate_signals(())
    except ValueError: pass
    else: raise AssertionError
