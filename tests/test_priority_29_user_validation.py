import pytest
from core.validation.user_validation import ValidationObservation,make_session,validation_summary
def test_validation_session_requires_identity_fields():
    with pytest.raises(ValueError): make_session("","engineer")
def test_blocker_prevents_beta_readiness():
    s=make_session("S1","engineer",[ValidationObservation("takeoff","failed","blocker","cannot complete")])
    assert not s.ready_for_beta and len(s.blockers)==1
def test_validation_summary_is_deterministic():
    s=make_session("S2","estimator",[ValidationObservation("boq","passed")])
    assert validation_summary(s)=={"session_id":"S2","tester_role":"estimator","observations":1,"blockers":0,"ready_for_beta":True}
