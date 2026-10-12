from core.workflow.hitl_v1 import Approval, Proposal, create_workflow, review, execute_approved

def proposal():
    return Proposal("p1","map_boq",("drawing-1",),{"item":"C30"},.92)

def test_proposals_start_pending():
    assert create_workflow([proposal()]).proposals[0].status=="pending"

def test_rejection_blocks_execution():
    w=review(create_workflow([proposal()]),[Approval("p1","engineer",False,"source mismatch")])
    try: execute_approved(w,"p1")
    except PermissionError: pass
    else: raise AssertionError("rejected proposal executed")

def test_explicit_approval_allows_execution():
    w=review(create_workflow([proposal()]),[Approval("p1","engineer",True,"verified drawing")])
    out=execute_approved(w,"p1")
    assert out["executed"] is True

def test_unknown_approval_fails():
    try: review(create_workflow([proposal()]),[Approval("x","engineer",True,"ok")])
    except ValueError: pass
    else: raise AssertionError("unknown approval accepted")

def test_reason_is_required():
    try: Approval("p1","engineer",True,"").validate()
    except ValueError: pass
    else: raise AssertionError("approval without reason accepted")

def test_low_confidence_is_still_pending():
    p=Proposal("p2","takeoff",("d1",),{"q":1},.2)
    assert create_workflow([p]).proposals[0].status=="pending"

def test_fingerprint_is_stable():
    a=create_workflow([proposal()]); b=create_workflow([proposal()])
    assert a.fingerprint==b.fingerprint
