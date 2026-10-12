import pytest
from core.twin.unified_aec_project_twin_v1 import TwinLink, fingerprint, link_element


def link(domain="structural", status="draft"):
    return TwinLink("l1","project-1","r1",domain,"drawing:A1","element-1","qty-1","boq-1",status)


def test_link_preserves_traceability():
    x=link_element(link())
    assert x.source_id=="drawing:A1"
    assert x.quantity_id=="qty-1"
    assert x.bo_q_id=="boq-1"
    assert x.status=="linked"


def test_invalid_domain_fails_closed():
    with pytest.raises(ValueError):
        link_element(link("unknown"))


def test_missing_identity_fails_closed():
    x=TwinLink("","","r1","structural","s","e","q","b")
    with pytest.raises(ValueError):
        fingerprint(x)


def test_fingerprint_deterministic():
    assert fingerprint(link()) == fingerprint(link())
