from decimal import Decimal
import pytest

from core.revision.intelligence_v2 import (
    RevisionElement, compare_revision_elements, summarize_revision, revision_fingerprint,
)


def el(rev, eid, qty, *, dims=(), rebar="0", boq="0", member="beam"):
    return RevisionElement(
        project_id="P1", revision=rev, element_id=eid, discipline="structural",
        member_type=member, description=eid, source_id=f"D-{rev}-{eid}", quantity=Decimal(qty),
        unit="m3", dimensions=tuple((k, Decimal(v)) for k, v in dims),
        rebar_weight_kg=Decimal(rebar), boq_quantity=Decimal(boq),
    )


def test_revision_detects_member_dimension_quantity_and_rebar_changes():
    before=(el("R1","E1","10",dims=(("length","5"),("width","2")),rebar="100",boq="10"),)
    after=(el("R2","E1","12",dims=(("length","6"),("width","2")),rebar="110",boq="12"),)
    changes=compare_revision_elements(before,after,project_id="P1",before_revision="R1",after_revision="R2")
    assert changes[0].change_type=="modified"
    assert set(changes[0].changed_fields)=={"quantity","rebar_weight_kg","boq_quantity","dimensions"}
    assert changes[0].dimension_changes[0] == ("length",Decimal("5"),Decimal("6"))


def test_added_removed_are_reviewable():
    before=(el("R1","E1","1"),)
    after=(el("R2","E2","2"),)
    changes=compare_revision_elements(before,after,project_id="P1",before_revision="R1",after_revision="R2")
    assert [x.change_type for x in changes]==["removed","added"]
    assert all(x.review_required for x in changes)


def test_duplicate_identity_fails_closed():
    with pytest.raises(ValueError):
        compare_revision_elements((el("R1","E1","1"),el("R1","E1","2")),(),project_id="P1",before_revision="R1",after_revision="R2")


def test_revision_mismatch_fails_closed():
    with pytest.raises(ValueError):
        compare_revision_elements((el("BAD","E1","1"),),(),project_id="P1",before_revision="R1",after_revision="R2")


def test_summary_and_fingerprint_are_deterministic():
    changes=compare_revision_elements((el("R1","E1","1"),),(el("R2","E1","2"),),project_id="P1",before_revision="R1",after_revision="R2")
    assert summarize_revision(changes)["quantity_delta"]==Decimal("1")
    assert revision_fingerprint(changes)==revision_fingerprint(changes)
