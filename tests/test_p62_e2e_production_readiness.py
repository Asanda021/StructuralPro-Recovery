from core.acceptance.e2e_production_readiness_v1 import GateEvidence, assess_e2e, validate_gates
def gate(status="pass"): return GateEvidence("takeoff-to-report",status,"test-evidence","2026-10-04T00:00:00Z")
def test_all_pass_go(): assert assess_e2e((gate(),)).decision=="go"
def test_fail_no_go(): assert assess_e2e((gate("fail"),)).decision=="no_go"
def test_unknown_needs_evidence(): assert assess_e2e((gate("unknown"),)).decision=="needs_evidence"
def test_empty_fail_closed():
    try: validate_gates(())
    except ValueError: pass
    else: raise AssertionError
def test_fingerprint_deterministic():
    assert assess_e2e((gate(),)).fingerprint==assess_e2e((gate(),)).fingerprint
