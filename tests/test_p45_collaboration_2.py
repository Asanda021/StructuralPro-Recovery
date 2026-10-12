import pytest
from core.collaboration.collaboration_v2 import *

def test_roles_review_and_activity_are_deterministic():
    members=[Member("u1","owner"),Member("u2","reviewer")]
    activity=Activity("a1","u1","edit","boq-1","src-1")
    assert approval_state(review_id="r1",reviewer_id="u2",decision="approved",source_id="src-2")["decision"]=="approved"
    assert collaboration_fingerprint("P1",members,[activity])==collaboration_fingerprint("P1",members,[activity])

def test_invalid_members_fail_closed():
    with pytest.raises(ValueError): validate_members([Member("u1","owner"),Member("u1","viewer")])
    with pytest.raises(ValueError): validate_members([Member("u1","editor")])
    with pytest.raises(ValueError): approval_state(review_id="r",reviewer_id="u",decision="yes",source_id="s")
