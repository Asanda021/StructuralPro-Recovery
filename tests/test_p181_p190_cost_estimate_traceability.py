from core.drawing.boq_propagation_v1 import BOQLineage
from core.drawing.cost_estimate_traceability_v1 import CostEstimateTraceabilityWorkflow, PriceEvidence

def boq(qty=10.0, bid="b1"):
    return BOQLineage(bid, "q1", "B1", ("s1",), "Beam concrete", qty, "m")

def price(amount=5.0, status="accepted", src=("price-sheet-1",)):
    return PriceEvidence("p1", "b1", amount, "IRR", src, .95, ("rejected" if not src else status)).validate()

def test_builds_traceable_estimate():
    out = CostEstimateTraceabilityWorkflow().build([boq()], [price()], [{"boq_id":"b1"}])
    assert len(out) == 1
    assert out[0].amount == 50
    assert "s1" in out[0].source_ids

def test_low_confidence_requires_review():
    out = CostEstimateTraceabilityWorkflow().build([boq()], [price()], [{"boq_id":"b1","confidence":.5}])
    assert out[0].status == "review"

def test_missing_price_source_rejects():
    out = CostEstimateTraceabilityWorkflow().build([boq()], [price(src=())], [{"boq_id":"b1"}])
    assert out[0].status == "rejected"

def test_quantity_revision_is_detected():
    w = CostEstimateTraceabilityWorkflow()
    old = w.build([boq(10)], [price()], [{"boq_id":"b1"}])
    new = w.build([boq(12)], [price()], [{"boq_id":"b1"}])
    assert w.impact(old, new)[0].impact == "quantity_changed"

def test_price_revision_is_detected():
    w = CostEstimateTraceabilityWorkflow()
    old = w.build([boq()], [price(5)], [{"boq_id":"b1"}])
    new = w.build([boq()], [price(6)], [{"boq_id":"b1"}])
    assert w.impact(old, new)[0].impact == "price_changed"

def test_removed_estimate_is_explicit():
    w = CostEstimateTraceabilityWorkflow()
    old = w.build([boq()], [price()], [{"boq_id":"b1"}])
    assert w.impact(old, ())[0].impact == "removed"

def test_stable_estimate_identity_for_quantity_change():
    w = CostEstimateTraceabilityWorkflow()
    old = w.build([boq(10)], [price()], [{"boq_id":"b1"}])
    new = w.build([boq(20)], [price()], [{"boq_id":"b1"}])
    assert old[0].estimate_id == new[0].estimate_id

def test_p171_boq_lineage_is_preserved():
    out = CostEstimateTraceabilityWorkflow().build([boq()], [price()], [{"boq_id":"b1"}])
    assert out[0].boq_id == "b1"
