"""Phase 12 golden quantity/BOQ validation tests."""
import pytest
from core.validation.golden import GoldenCase, validate_case

def case():
    return GoldenCase(
        "GOLDEN-001","2026.10",{"name":"Demo","discipline":"structural"},
        (
            {"object_id":"C1","concrete_volume_m3":12.50,"rebar_weight_kg":980.0},
            {"object_id":"B1","concrete_volume_m3":4.20,"rebar_weight_kg":320.0},
        ),
        (
            {"item_code":"CONC-01","quantity":16.70,"unit":"m3","total":83500.0},
            {"item_code":"REBAR-01","quantity":1300.0,"unit":"kg","total":78000.0},
        ),
        {"concrete_volume_m3":0.001,"rebar_weight_kg":0.1,"quantity":0.01,"total":1.0},
    )

def test_exact_case_passes():
    r=validate_case(case(),
        [{"object_id":"C1","concrete_volume_m3":12.5,"rebar_weight_kg":980},{"object_id":"B1","concrete_volume_m3":4.2,"rebar_weight_kg":320}],
        [{"item_code":"CONC-01","quantity":16.7,"unit":"m3","total":83500},{"item_code":"REBAR-01","quantity":1300,"unit":"kg","total":78000}])
    assert r.passed and r.issue_count==0 and len(r.expected_digest)==64

def test_tolerance_is_explicit():
    r=validate_case(case(),
        [{"object_id":"C1","concrete_volume_m3":12.5005,"rebar_weight_kg":980.09},{"object_id":"B1","concrete_volume_m3":4.2,"rebar_weight_kg":320}],
        [{"item_code":"CONC-01","quantity":16.7001,"unit":"m3","total":83500.5},{"item_code":"REBAR-01","quantity":1300,"unit":"kg","total":78000}])
    assert r.passed

def test_missing_unexpected_and_mismatch_are_reported():
    r=validate_case(case(),
        [{"object_id":"C1","concrete_volume_m3":13.0,"rebar_weight_kg":980},{"object_id":"X1","concrete_volume_m3":1.0,"rebar_weight_kg":10}],
        [{"item_code":"CONC-01","quantity":16.7,"unit":"m3","total":83500},{"item_code":"REBAR-01","quantity":1290,"unit":"kg","total":78000}])
    assert not r.passed
    found={(i.category,i.key,i.field) for i in r.issues}
    assert ("quantities","B1","__row__") in found
    assert ("quantities","X1","__row__") in found
    assert ("quantities","C1","concrete_volume_m3") in found
    assert ("boq","REBAR-01","quantity") in found

def test_duplicate_identity_is_rejected():
    with pytest.raises(ValueError,match="duplicate row identity"):
        validate_case(case(),[{"object_id":"C1"},{"object_id":"C1"}],[])

def test_invalid_tolerance_is_rejected():
    with pytest.raises(ValueError,match="invalid tolerance"):
        GoldenCase("X","1",{},tolerances={"quantity":-0.1})


def test_golden_contract_matches_authoritative_quantity_core_and_boq():
    from core.takeoff.construction_core import ConstructionQuantityCore
    from core.takeoff.element_model import ConstructionElement
    from core.takeoff.estimate import build_estimate

    element=ConstructionElement(
        id="C1", kind="column", length_m=2.0, width_m=0.3,
        height_m=0.3, quantity_count=10, source_id="golden:C1"
    )
    line=ConstructionQuantityCore.rectangular_volume(element)
    assert line.quantity == pytest.approx(1.8, abs=1e-12)
    estimate=build_estimate([line], aggregate=True)
    actual=[{
        "object_id":line.element_id,
        "item_code":line.item_code,
        "quantity":line.quantity,
        "unit":line.unit,
        "description":line.description,
    }]
    expected=[{
        "object_id":"C1",
        "item_code":"CONCRETE",
        "quantity":1.8,
        "unit":"m3",
        "description":"Concrete volume",
    }]
    result=validate_case(
        GoldenCase(
            "GOLDEN-CORE-001","2026.10",{"source":"authoritative-core"},
            tuple(expected), tuple(estimate["boq"]), {"quantity": 1e-12}
        ),
        actual,
        estimate["boq"],
    )
    assert result.passed
