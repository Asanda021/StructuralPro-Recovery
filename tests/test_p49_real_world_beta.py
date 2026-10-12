import pytest
from core.beta.real_world_beta_v2 import *
def case(m=98): return BetaCase("c1","p1","human_takeoff",100,m,"m3")
def test_error_and_accuracy():
    assert absolute_error(case())==2
    assert relative_error(case())==.02
    a=aggregate_accuracy([case()]); assert a["case_count"]==1 and a["max_relative_error"]==.02
def test_zero_reference_is_explicit():
    assert relative_error(BetaCase("c","p","sheet",0,0,"m2"))==0
    assert relative_error(BetaCase("c","p","sheet",0,1,"m2"))==float("inf")
def test_review_and_fingerprint_fail_closed():
    r=BetaReview("c1","r1","accepted","checked against human takeoff")
    validate_review(r); assert beta_fingerprint([case()],[r])
    with pytest.raises(BetaEvidenceError): validate_review(BetaReview("","","accepted","x"))
