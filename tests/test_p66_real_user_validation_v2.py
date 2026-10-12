from core.beta.real_user_validation_v2 import *
def r(q=100,s=102,d="accepted"): return UserTaskEvidence("p1","u1","takeoff",q,s,"m3","user-record","2026-10-04",d)
def test_accept(): assert assess((r(),))["disposition"]=="accepted"
def test_review(): assert assess((r(s=120),))["disposition"]=="review"
def test_needs_evidence(): assert assess((r(d="needs_evidence"),))["disposition"]=="needs_evidence"
def test_invalid_disposition():
    try: validate((r(d="x"),))
    except ValueError: return
    assert False
