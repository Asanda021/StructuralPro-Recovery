from core.acceptance.p115_p119 import run_all

def test_p115_p119_production_acceptance():
    result=run_all()
    assert result["P115"]["verified"] is True
    assert result["P115"]["grand_total"] == 1100
    assert result["P116"]["verified"] is True
    assert result["P116"]["scenario_count"] >= 6
    assert result["P117"]["verified"] is True
    assert result["P117"]["quantity_total"] == 260
    assert result["P118"]["verified"] is True
    assert result["P118"]["formats"] == ["xlsx","pdf","json"]
    assert result["P119"]["verified"] is True
    assert result["P119"]["edges"] == 3
