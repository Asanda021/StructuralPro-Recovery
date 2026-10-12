from core.takeoff.unified_2d_bim_takeoff_v1 import Record,fingerprint
import pytest
def r(i="1",v=1,status="accepted"): return Record(i,("S1",),v,"unit","A",status)
def test_valid(): assert r().validate()
def test_invalid_source():
    with pytest.raises(ValueError): Record("1",(),1,"u","A").validate()
def test_review_blocked():
    with pytest.raises(ValueError): r(status="review").validate()
def test_deterministic(): assert fingerprint([r("b"),r("a")])==fingerprint([r("a"),r("b")])
