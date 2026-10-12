from decimal import Decimal
import pytest
from core.revision.revision_impact_v1 import RevisionSnapshot, compare_revisions
from core.revision.revision_closure_v1 import build_revision_closure, validate_revision_closure

def snap(record, rev, element, qty, boq, est, cost):
    return RevisionSnapshot(record,"P1",rev,"src",element,Decimal(qty),Decimal(boq),Decimal(est),Decimal(cost))

def test_revision_closure_is_deterministic_and_closed():
    old=[snap("r1","R1","B1","10","10","100","80")]
    new=[snap("r2","R2","B1","12","12","120","95"),snap("r3","R2","C1","5","5","50","40")]
    report=compare_revisions(old,new,"R1","R2")
    a=build_revision_closure(report,{"B1":"accepted","C1":"rejected"})
    b=build_revision_closure(report,{"B1":"accepted","C1":"rejected"})
    assert a==b
    assert validate_revision_closure(a)["closed"] is True

def test_missing_review_fails_closed():
    report=compare_revisions([snap("r1","R1","B1","10","10","100","80")], [snap("r2","R2","B1","12","12","120","95")],"R1","R2")
    with pytest.raises(ValueError): build_revision_closure(report,{})

def test_open_review_is_not_closed():
    report=compare_revisions([snap("r1","R1","B1","10","10","100","80")], [snap("r2","R2","B1","12","12","120","95")],"R1","R2")
    closure=build_revision_closure(report,{"B1":"open"})
    assert validate_revision_closure(closure)["closed"] is False

def test_tampering_is_detected():
    report=compare_revisions([snap("r1","R1","B1","10","10","100","80")], [snap("r2","R2","B1","12","12","120","95")],"R1","R2")
    closure=build_revision_closure(report,{"B1":"accepted"})
    closure["totals"]["quantity_delta"]=Decimal("999")
    with pytest.raises(ValueError): validate_revision_closure(closure)
