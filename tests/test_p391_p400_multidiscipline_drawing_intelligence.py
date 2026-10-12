from core.drawing.multidiscipline_intelligence_v1 import MultiDisciplineDrawingIntelligence
import pytest

def c(w,sid="S1",d="structural",cat="beam",typ="beam",conf=.95,e=("explicit layer",)):
    return w.classify(sid,discipline=d,category=cat,element_type=typ,evidence=e,confidence=conf)

def test_all_building_disciplines():
    w=MultiDisciplineDrawingIntelligence()
    rows=[c(w,str(i),d, "item","item") for i,d in enumerate(("structural","architectural","mechanical","electrical","site"))]
    assert {x.discipline for x in rows}=={"structural","architectural","mechanical","electrical","site"}

def test_ambiguous_input_stays_review_or_rejected():
    w=MultiDisciplineDrawingIntelligence()
    assert c(w,conf=.79).status=="review"
    assert w.classify("S2",discipline="structural",category="beam",element_type="beam",confidence=.95).status=="review"

def test_missing_classification_fails_closed():
    w=MultiDisciplineDrawingIntelligence()
    assert w.classify("S1").status=="rejected"

def test_invalid_discipline_rejected_by_contract():
    with pytest.raises(ValueError):
        MultiDisciplineDrawingIntelligence().classify("S1",discipline="unknown",category="x",element_type="x",evidence=("label",),confidence=.9)

def test_fingerprint_is_deterministic():
    w=MultiDisciplineDrawingIntelligence(); a=c(w,"A"); b=c(w,"B")
    assert w.fingerprint((a,b))==w.fingerprint((b,a))

def test_revision_reconciliation():
    w=MultiDisciplineDrawingIntelligence(); old=c(w); new=c(w,cat="column",typ="column")
    assert w.reconcile((old,),(new,))[0][1]=="changed"
    assert "category" in w.reconcile((old,),(new,))[0][2]

def test_add_remove_are_explicit():
    w=MultiDisciplineDrawingIntelligence(); a=c(w,"A"); b=c(w,"B")
    assert w.reconcile((a,),(a,b))==(("A","unchanged",()),("B","added"))
