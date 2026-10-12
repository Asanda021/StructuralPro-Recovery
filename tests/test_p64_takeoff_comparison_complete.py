from core.verification.takeoff_comparison_v1 import Comparison, compare

def test_accept():
    assert compare((Comparison('p','C01','m3',10,10,.05),))['decision']=='accepted'

def test_review():
    assert compare((Comparison('p','C01','m3',10,11,.05),))['decision']=='review'

def test_zero_reference_rejected():
    try:
        compare((Comparison('p','C01','m3',0,1,.05),))
    except ValueError:
        return
    raise AssertionError

def test_deterministic():
    x=Comparison('p','C01','m3',10,10,.05)
    assert compare((x,))['fingerprint']==compare((x,))['fingerprint']
