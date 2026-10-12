from core.drawing.models import EngineeringElement
from core.drawing.takeoff_traceability_v1 import TakeoffTraceabilityWorkflow


def element(element_id="B1", sources=("s1",), confidence=0.95):
    return EngineeringElement(
        element_id=element_id, domain="beams", kind="beam",
        source_ids=sources, geometry={"length": 6.0},
        confidence=confidence, evidence=("explicit member tag",)
    )


def test_accepts_explicit_quantity_with_lineage():
    w = TakeoffTraceabilityWorkflow()
    qs, links = w.build([element()], [{"element_id": "B1", "quantity": 6.0, "unit": "m", "formula": "drawing length"}])
    assert qs[0].status == "accepted"
    assert any(x.relation == "source_to_element" for x in links)
    assert any(x.relation == "element_to_quantity" for x in links)


def test_low_confidence_requires_review():
    w = TakeoffTraceabilityWorkflow()
    qs, _ = w.build([element(confidence=0.5)], [{"element_id": "B1", "quantity": 6.0, "unit": "m"}])
    assert qs[0].status == "review"


def test_missing_source_fails_closed():
    w = TakeoffTraceabilityWorkflow()
    qs, _ = w.build([element(sources=())], [{"element_id": "B1", "quantity": 6.0, "unit": "m"}])
    assert qs[0].status == "rejected"


def test_missing_quantity_is_rejected():
    w = TakeoffTraceabilityWorkflow()
    qs, _ = w.build([element()], [{"element_id": "B1", "unit": "m"}])
    assert qs[0].status == "rejected"


def test_revision_impact_is_deterministic():
    w = TakeoffTraceabilityWorkflow()
    old, _ = w.build([element()], [{"element_id": "B1", "quantity": 6.0, "unit": "m"}])
    new, _ = w.build([element()], [{"element_id": "B1", "quantity": 7.0, "unit": "m"}])
    impact = w.revision_impact(old, new)
    assert impact[0].impact == "quantity_changed"
    assert impact[0].changed_fields == ("quantity",)


def test_boq_link_requires_accepted_quantity():
    w = TakeoffTraceabilityWorkflow()
    qs, links = w.build([element()], [{"element_id": "B1", "quantity": 6.0, "unit": "m"}],
                         [{"source": "B1", "quantity": 6.0, "unit": "m"}])
    assert qs[0].status == "accepted"
    assert any(x.relation == "quantity_to_boq" for x in links)


def test_p151_compatibility_preserves_provenance_boundary():
    w = TakeoffTraceabilityWorkflow()
    qs, _ = w.build([element()], [{"element_id": "B1", "quantity": 6.0, "unit": "m"}])
    assert qs[0].source_ids == ("s1",)
