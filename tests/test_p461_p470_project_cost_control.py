from core.cost_control.project_cost_control_v1 import CostRecord,fingerprint
import pytest
def r(i="1",a=10,status="accepted"): return CostRecord(i,("S1",),a,"IRR","A",status)
def test_valid(): assert r().validate()
def test_source_required():
    with pytest.raises(ValueError): CostRecord("1",(),10,"IRR","A").validate()
def test_review_blocked():
    with pytest.raises(ValueError): r(status="review").validate()
def test_negative_blocked():
    with pytest.raises(ValueError): r(a=-1).validate()
def test_deterministic(): assert fingerprint([r("b"),r("a")])==fingerprint([r("a"),r("b")])
