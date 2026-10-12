import pytest
from core.collaboration import *

def setup():
 w=CollaborationWorkspace(); w.add_role(Role("engineer",frozenset({"edit","review"}))); w.add_user(User("U1","Mohammad","engineer")); w.create_object("P1",{"quantity":10}); return w

def test_users_roles_assign_comments_reviews_notifications_and_activity():
 w=setup(); w.assign(Assignment("A1","U1","P1")); w.comment(Comment("C1","U1","P1","reviewed")); w.review(Review("R1","P1","U1","approved")); w.notify(Notification("N1","U1","review","P1")); w.update_object("U1","P1",{"quantity":12},1)
 assert w.snapshot()=={"users":1,"objects":1,"assignments":1,"comments":1,"reviews":1,"notifications":1,"activities":1}

def test_optimistic_concurrency_rejects_stale_write():
 w=setup(); w.update_object("U1","P1",{"quantity":11},1)
 with pytest.raises(RuntimeError,match="version_conflict"): w.update_object("U1","P1",{"quantity":12},1)

def test_permission_is_enforced():
 w=CollaborationWorkspace(); w.add_role(Role("viewer",frozenset())); w.add_user(User("U","Viewer","viewer")); w.create_object("P",{})
 with pytest.raises(PermissionError): w.update_object("U","P",{},1)
