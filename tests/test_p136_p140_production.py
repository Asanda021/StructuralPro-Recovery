from core.ai.p136_p140 import Evidence, EstimateFact, QuantityFact, build_context, deterministic_digest, run_quality_gate

def test_context_is_traced_and_deterministic():
    ctx = build_context("PRJ-1", "quantity+estimate", [Evidence("A", "drawing", "beam")],
                        [QuantityFact("Concrete", 10, "m3", "A")])
    assert run_quality_gate(ctx)["status"] == "pass"
    assert deterministic_digest(ctx) == deterministic_digest(ctx)

def test_missing_items_are_review_findings():
    ctx = build_context("PRJ-2", "takeoff", [Evidence("A", "drawing")])
    result = run_quality_gate(ctx, ["Concrete", "Rebar"])
    assert result["status"] == "review" and result["warnings"] == 2

def test_cross_source_conflict_is_detected():
    ctx = build_context("PRJ-3", "takeoff", [Evidence("A", "drawing"), Evidence("B", "drawing")],
                        [QuantityFact("Beam", 10, "m3", "A"), QuantityFact("Beam", 12, "m3", "B")])
    assert any(x["code"] == "P138-CROSS-SOURCE-CONFLICT" for x in run_quality_gate(ctx)["findings"])

def test_specification_gap_is_visible():
    ctx = build_context("PRJ-4", "specification", [Evidence("spec", "spec", "")])
    assert any(x["code"] == "P139-NO-SPECIFICATION-TEXT" for x in run_quality_gate(ctx)["findings"])

def test_unpriced_estimate_fails_closed():
    ctx = build_context("PRJ-5", "estimate", [Evidence("boq", "boq")],
                        estimates=[EstimateFact("Concrete", 10, "m3", None, "boq")])
    result = run_quality_gate(ctx)
    assert result["status"] == "fail"
    assert any(x["code"] == "P140-UNPRICED-ESTIMATE" for x in result["findings"])

def test_negative_quantity_fails_closed():
    ctx = build_context("PRJ-6", "takeoff", [Evidence("A", "drawing")],
                        [QuantityFact("Concrete", -1, "m3", "A")])
    assert run_quality_gate(ctx)["status"] == "fail"
