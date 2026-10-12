"""Priority 46 — calculation and quantity integrity audit."""
import math
import pytest
from core.takeoff.boq import build_boq, validate_boq_structure
from core.takeoff.costing import cost_breakdown

def test_boq_rejects_non_finite_total():
    with pytest.raises(ValueError, match="total"):
        build_boq([{"description":"X","unit":"m","quantity":1e308,"unit_price":1e308}])

def test_cost_breakdown_rejects_non_finite_inputs():
    with pytest.raises(ValueError, match="quantity"):
        cost_breakdown([{"description":"X","unit":"m","quantity":math.nan,"unit_price":1}])
    with pytest.raises(ValueError, match="factor rate"):
        cost_breakdown([{"description":"X","unit":"m","quantity":1,"unit_price":1}], factors={"bad":math.inf})

def test_boq_structure_flags_invalid_total():
    result=validate_boq_structure([{"description":"X","unit":"m","quantity":1,"total":math.inf}])
    assert not result["valid"]
    assert any(x["code"]=="invalid_total" for x in result["errors"])
