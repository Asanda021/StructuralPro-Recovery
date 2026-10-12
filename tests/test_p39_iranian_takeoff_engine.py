from core.iran.takeoff_engine_v2 import ExecutionRule, build_iranian_boq, price_boq
from core.iran.data import IranDataRegistry, AdjustmentIndex

def test_boq_and_waste_are_deterministic():
    rows=build_iranian_boq("تیر",{"length":5,"width":.3,"height":.5},waste_factor=.1,
                            rules=[ExecutionRule("R","rule",1.02)])
    assert rows and rows[0]["quantity"] > 0
    assert rows[0]["source"]=="iranian-takeoff-engine-v2"

def test_pricing_fails_closed_without_official_price():
    reg=IranDataRegistry()
    rows=[{"quantity":10,"item_code":"X"}]
    assert price_boq(rows,reg,year=1404,quarter=1,discipline="ابنیه")[0]["amount"] is None

def test_adjustment_requires_registered_source():
    reg=IranDataRegistry()
    reg.add_adjustment_index(AdjustmentIndex(1404,1,"ابنیه",1.2,"official-x",provisional=True))
    rows=price_boq([{"quantity":2,"unit_price":100}],reg,year=1404,quarter=1,discipline="ابنیه")
    assert rows[0]["amount"]==240
