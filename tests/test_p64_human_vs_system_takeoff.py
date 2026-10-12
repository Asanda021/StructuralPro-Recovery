from core.verification.human_vs_system_takeoff_v1 import TakeoffComparison,compare
def i(h,s,t=.05,code="C01"): return TakeoffComparison("p1",code,"m3",h,s,t)
def test_exact_accepted(): assert compare((i(10,10),)).decision=="accepted"
def test_within_tolerance(): assert compare((i(10,10.4,.05),)).passed_count==1
def test_outside_tolerance_review(): assert compare((i(10,11,.05),)).decision=="review"
def test_zero_reference_fail_closed():
    try: compare((i(0,1),))
    except ValueError: pass
    else: raise AssertionError
def test_deterministic(): assert compare((i(10,10),)).fingerprint==compare((i(10,10),)).fingerprint
