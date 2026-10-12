from core.acceptance.p110_p114 import run_all


def test_p110_p114_production_acceptance():
    result = run_all()

    assert result["P110"]["verified"] is True
    assert result["P110"]["quantity_delta"] == 2
    assert result["P110"]["rebar_delta_kg"] == 10
    assert result["P110"]["boq_delta"] == 2

    assert result["P111"]["verified"] is True
    assert result["P111"]["base"] == 1000
    assert result["P111"]["grand_total"] == 1100

    assert result["P112"]["verified"] is True
    assert result["P112"]["components"] == ["CON", "REBAR", "LAB-CON"]

    assert result["P113"]["verified"] is True
    assert result["P113"]["delta"] == 200

    assert result["P114"]["verified"] is True
    assert result["P114"]["scenario_count"] >= 5
