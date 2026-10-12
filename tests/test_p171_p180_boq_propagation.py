import math
import pytest

from core.drawing.boq_propagation_v1 import BOQPropagationWorkflow, BOQLineage
from core.drawing.takeoff_traceability_v1 import QuantityEvidence


def q(qid="q1", qty=10.0, unit="m", src=("s1",), status="accepted", confidence=.95):
    return QuantityEvidence(qid, "B1", src, qty, unit, confidence, "formula", status).validate()


def test_builds_auditable_boq_line():
    out = BOQPropagationWorkflow().build([q()], [{"quantity_id": "q1", "description": "Beam concrete"}])
    assert len(out) == 1 and out[0].source_ids == ("s1",)


def test_low_confidence_is_review():
    out = BOQPropagationWorkflow().build([q()], [{"quantity_id": "q1", "description": "Beam", "confidence": .5}])
    assert out[0].status == "review"


def test_missing_source_rejects_line():
    out = BOQPropagationWorkflow().build([q(src=())], [{"quantity_id": "q1", "description": "Beam"}])
    assert out[0].status == "rejected"


def test_revision_quantity_impact():
    workflow = BOQPropagationWorkflow()
    old = workflow.build([q(qty=10)], [{"quantity_id": "q1", "description": "Beam"}])
    new = workflow.build([q(qty=12)], [{"quantity_id": "q1", "description": "Beam"}])
    assert workflow.impact(old, new)[0].impact == "quantity_changed"


def test_removed_line_is_explicit():
    old = (BOQLineage("b1", "q1", "B1", ("s1",), "Beam", 10, "m"),)
    assert BOQPropagationWorkflow.impact(old, ())[0].impact == "removed"


def test_deterministic_order():
    workflow = BOQPropagationWorkflow()
    out = workflow.build([q("q2"), q("q1")], [
        {"quantity_id": "q2", "description": "Z"},
        {"quantity_id": "q1", "description": "A"},
    ])
    assert [x.boq_id for x in out] == sorted(x.boq_id for x in out)


def test_p171_lineage_preserved():
    assert BOQPropagationWorkflow().build([q()], [{"quantity_id": "q1", "description": "Beam"}])[0].quantity_id == "q1"


def test_p172_fingerprints_are_stable():
    workflow = BOQPropagationWorkflow()
    lines = workflow.build([q()], [{"quantity_id": "q1", "description": "Beam"}])
    assert workflow.fingerprints(lines) == workflow.fingerprints(lines)


def test_p173_unresolved_is_fail_closed():
    workflow = BOQPropagationWorkflow()
    lines = workflow.build([q()], [{"quantity_id": "q1", "description": ""}])
    assert lines[0].status == "rejected" and workflow.unresolved(lines)


def test_p174_source_change_requires_review():
    workflow = BOQPropagationWorkflow()
    old = workflow.build([q(src=("s1",))], [{"quantity_id": "q1", "description": "Beam"}])
    new = workflow.build([q(src=("s2",))], [{"quantity_id": "q1", "description": "Beam"}])
    assert workflow.impact(old, new)[0].impact == "review_required"


def test_p175_source_conflict_is_explicit():
    lines = (BOQLineage("b1", "q1", "B1", ("s1", "s2"), "Beam", 10, "m"),)
    assert BOQPropagationWorkflow.source_conflicts(lines) == ("B1",)


@pytest.mark.parametrize("quantity", [math.nan, math.inf, -math.inf, -1, True, "not-a-number"])
def test_boq_lineage_rejects_invalid_quantity(quantity):
    line = BOQLineage("b1", "q1", "B1", ("s1",), "Beam", quantity, "m")
    with pytest.raises(ValueError, match="quantity"):
        line.validate()


@pytest.mark.parametrize("quantity", [math.nan, math.inf, -math.inf, -1, True, "not-a-number"])
def test_propagation_rejects_invalid_override_quantity(quantity):
    with pytest.raises(ValueError, match="quantity"):
        BOQPropagationWorkflow().build([q()], [
            {"quantity_id": "q1", "description": "Beam", "quantity": quantity}
        ])


@pytest.mark.parametrize("confidence", [math.nan, math.inf, -math.inf, -0.1, 1.01, True, "bad"])
def test_propagation_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError, match="confidence"):
        BOQPropagationWorkflow().build([q()], [
            {"quantity_id": "q1", "description": "Beam", "confidence": confidence}
        ])


@pytest.mark.parametrize("threshold", [math.nan, math.inf, -math.inf, -0.1, 1.01, True])
def test_workflow_rejects_invalid_confidence_threshold(threshold):
    with pytest.raises(ValueError, match="confidence threshold"):
        BOQPropagationWorkflow(accept_confidence=threshold)


def test_duplicate_quantity_identity_is_not_silently_overwritten():
    with pytest.raises(ValueError, match="duplicate quantity identity"):
        BOQPropagationWorkflow().build([q(), q()], [{"quantity_id": "q1", "description": "Beam"}])


def test_revision_impact_rejects_invalid_prior_line():
    bad = BOQLineage("b1", "q1", "B1", ("s1",), "Beam", math.nan, "m")
    with pytest.raises(ValueError, match="quantity"):
        BOQPropagationWorkflow.impact((bad,), ())
