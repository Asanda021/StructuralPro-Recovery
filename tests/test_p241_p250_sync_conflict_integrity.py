import pytest
from core.sync.conflicts import merge_dict
from core.sync.conflict_integrity_v1 import collect_conflicts,resolve_all,fingerprint
def test_conflict_is_explicit_and_resolvable():
 m,c=merge_dict({"a":1},{"a":2},{"a":3})
 assert c==["a"]; assert len(collect_conflicts(m))==1
 assert resolve_all(m,{"a":"local"})["a"]==2
def test_unknown_choice_fails():
 m,_=merge_dict({"a":1},{"a":2},{"a":3})
 with pytest.raises(ValueError): resolve_all(m,{"a":"bad"})
def test_unknown_path_fails():
 m,_=merge_dict({"a":1},{"a":2},{"a":3})
 with pytest.raises(ValueError): resolve_all(m,{"x":"local"})
def test_fingerprint_stable(): assert fingerprint({"b":2,"a":1})==fingerprint({"a":1,"b":2})