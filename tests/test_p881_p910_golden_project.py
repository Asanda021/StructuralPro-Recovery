import pytest
from core.validation.golden_project_acceptance_v1 import build_golden_project, validate_golden_project

def data():
    return {"quantity":{"concrete_m3":100},"boq":{"items":4},"estimate":{"total":500},"report":{"rtl":True},"revision":{"id":"R2"}}

def test_golden_project_is_deterministic():
    a=build_golden_project(project_id="GOLDEN-001",revision="R2",sections=data())
    b=build_golden_project(project_id="GOLDEN-001",revision="R2",sections=data())
    assert a==b
    assert validate_golden_project(a)["valid"] is True

def test_missing_section_fails_closed():
    d=data(); d.pop("report")
    with pytest.raises(ValueError): build_golden_project(project_id="G",revision="R1",sections=d)

def test_tampering_is_detected():
    g=build_golden_project(project_id="G",revision="R1",sections=data())
    g["sections"]["quantity"]["concrete_m3"]=999
    with pytest.raises(ValueError): validate_golden_project(g)

def test_identity_is_required():
    with pytest.raises(ValueError): build_golden_project(project_id="",revision="R1",sections=data())
