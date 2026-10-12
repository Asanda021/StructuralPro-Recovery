import pytest
from core.takeoff.costing import cost_breakdown
from core.takeoff.estimate import build_estimate
from core.takeoff.boq import build_boq
def test_factor_audit_trail_is_sequential_and_explicit():
    rows=build_boq([{"item_code":"A","description":"Concrete","quantity":10,"unit":"m3","unit_price":100}],aggregate=False)
    cost=cost_breakdown(rows,{"overhead":0.10,"profit":0.05,"tax":0.09})
    assert cost["base"]==1000
    assert [x["name"] for x in cost["factor_sequence"]]==["overhead","profit","tax"]
    assert cost["factor_sequence"][0]["delta"]==pytest.approx(100)
    assert cost["factor_sequence"][1]["base"]==pytest.approx(1100)
    assert cost["grand_total"]==pytest.approx(1258.95)
def test_estimate_exposes_finalization_and_factor_audit():
    result=build_estimate([{"item_code":"A","description":"Concrete","quantity":2,"unit":"m3","unit_price":100}],factors={"overhead":0.1,"profit":0.05})
    assert result["finalizable"] is True and result["cost"]["factor_sequence"][0]["rate"]==0.1
def test_invalid_boq_is_not_finalizable():
    with pytest.raises(ValueError, match="description is required"):
        build_estimate([{"description":"","quantity":1,"unit":"m3"}])
