from core.beta.user_validation_v1 import UserValidationEvidence, evaluate, validate_evidence

def ev(system=100.0, disposition="accepted"):
    return UserValidationEvidence("P59-PROJECT","reviewer-1","concrete",100.0,system,"m3","human-reference","2026-10-04T00:00:00Z",disposition)

def test_evaluation_is_deterministic():
    a=evaluate((ev(102),)); b=evaluate((ev(102),))
    assert a==b
    assert a.sample_count==1 and a.mean_relative_error==0.02

def test_missing_evidence_fails_closed():
    try: validate_evidence(())
    except ValueError: pass
    else: raise AssertionError("missing evidence must fail closed")

def test_negative_quantities_fail_closed():
    try: validate_evidence((ev(-1),))
    except ValueError: pass
    else: raise AssertionError("negative quantity must fail closed")

def test_needs_evidence_propagates():
    assert evaluate((ev(100,"needs_evidence"),)).disposition=="needs_evidence"
