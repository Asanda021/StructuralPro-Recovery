from core.boq.evidence_first_boq_v1 import EvidenceBOQLine,build,fingerprint
import pytest
def l(i="L1",q="Q1",src=("S1",),n=2,status="accepted"): return EvidenceBOQLine(i,q,src,"item",n,"m3","A",status)
def test_build_preserves_evidence(): assert build([l()])[0].source_ids==("S1",)
def test_missing_source_fails(): 
    with pytest.raises(ValueError): l(src=()).validate()
def test_review_blocked():
    with pytest.raises(ValueError): l(status="review").validate()
def test_deterministic_fingerprint(): assert fingerprint([l("B"),l("A")])==fingerprint([l("A"),l("B")])
def test_negative_blocked():
    with pytest.raises(ValueError): l(n=-1).validate()
