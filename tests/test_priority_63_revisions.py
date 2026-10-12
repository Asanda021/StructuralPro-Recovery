from core.platform.revisions import create_revision,verify_revision,compare_revisions

def test_revision_is_immutable_and_integrity_is_verifiable():
    payload={"qty":10,"items":[1,2]}
    rev=create_revision(payload,1,message="initial")
    payload["qty"]=99
    assert verify_revision(rev)
    assert rev.payload["qty"]==10

def test_tampering_is_detected():
    rev=create_revision({"qty":10},1,message="initial")
    rev.payload["qty"]=11
    assert not verify_revision(rev)

def test_revision_comparison_is_deterministic():
    a=create_revision({"qty":10},1,message="a")
    b=create_revision({"qty":12},2,parent_id=1,message="b")
    result=compare_revisions(a,b)
    assert result["same"] is False
    assert result["left_revision"]==1 and result["right_revision"]==2

def test_invalid_message_fails_closed():
    try: create_revision({},1,message="")
    except ValueError: pass
    else: raise AssertionError("empty revision message must fail")
