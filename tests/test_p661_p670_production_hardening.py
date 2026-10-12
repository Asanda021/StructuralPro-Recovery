from core.platform.production_hardening_v1 import PerformanceBudget, SecurityPolicy, ProductionGuard, recover_state

def guard():
    return ProductionGuard(PerformanceBudget(.5,10),SecurityPolicy())

def test_source_is_required():
    try: guard().validate_payload({"value":1})
    except PermissionError: pass
    else: raise AssertionError("source requirement bypassed")

def test_network_is_denied_by_default():
    try: guard().validate_payload({"source_id":"s","network_required":True})
    except PermissionError: pass
    else: raise AssertionError("network policy bypassed")

def test_payload_limit_is_enforced():
    g=ProductionGuard(PerformanceBudget(.5,10),SecurityPolicy(max_payload_bytes=20))
    try: g.validate_payload({"source_id":"s","data":"x"*100})
    except ValueError: pass
    else: raise AssertionError("payload limit bypassed")

def test_health_is_green_for_fast_success():
    s=guard().run([1,2,3],lambda _:None)
    assert s.ok and s.item_count==3 and not s.errors

def test_worker_errors_fail_health_closed():
    s=guard().run([1],lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    assert not s.ok and s.errors

def test_item_budget_is_enforced():
    try: guard().run(list(range(11)),lambda _:None)
    except ValueError: pass
    else: raise AssertionError("item budget bypassed")

def test_recovery_requires_complete_snapshot():
    try: recover_state({"project":"x"},("project","revision"))
    except ValueError: pass
    else: raise AssertionError("incomplete recovery accepted")

def test_recovery_is_deterministic():
    assert recover_state({"project":"x","revision":3},("project","revision"))=={"project":"x","revision":3}

def test_invalid_budget_fails():
    try: PerformanceBudget(0,1).validate()
    except ValueError: pass
    else: raise AssertionError("invalid budget accepted")

def test_health_fingerprint_is_reproducible_shape():
    a=guard().run([],lambda _:None); b=guard().run([],lambda _:None)
    assert len(a.fingerprint)==64 and len(b.fingerprint)==64
