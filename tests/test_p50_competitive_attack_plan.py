import pytest
from core.competitive.competitive_attack_plan_v2 import *
def ev(c="PlanSwift",cap="takeoff"): return CompetitorEvidence(c,cap,"official-doc","supported","2026-10-04")
def test_matrix_and_fingerprint():
    dims=[BenchmarkDimension("takeoff",1),BenchmarkDimension("reporting",1)]
    m=build_matrix([ev()],dims); assert len(m["takeoff"])==1 and m["reporting"]==[]
    assert len(plan_fingerprint([ev()],dims))==64
def test_missing_evidence_is_not_claimed():
    assert unsupported_claims([ev()],[("PlanSwift","pricing"),("PlanSwift","takeoff")])==[("PlanSwift","pricing")]
def test_invalid_evidence_fails_closed():
    with pytest.raises(CompetitivePlanError): validate_evidence(CompetitorEvidence("","","","",""))
    with pytest.raises(CompetitivePlanError): validate_dimensions([])
