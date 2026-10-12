import pytest
from core.technical_office import *

def test_measurement_and_quantity_change_are_traceable():
    m=MeasurementRecord("M1","A01","Concrete",12,"m3",source_id="BOQ-1")
    c=QuantityChange("Q1","A01",10,12,"approved drawing revision")
    assert m.source_id=="BOQ-1" and c.delta==2

def test_progress_calculates_only_current_period():
    r=TechnicalOfficeEngine.progress_amount([{"item_code":"A","quantity":12,"unit_price":100}],previous={"A":10})
    assert r["total"]==pytest.approx(200)
    assert r["rows"][0]["period_quantity"]==2

def test_adjustment_and_payment_certificate():
    a=AdjustmentRecord("AD1",1000,120,100)
    assert a.amount==pytest.approx(200)
    d=Deduction("D1","insurance",50)
    p=TechnicalOfficeEngine.payment_certificate(1000,[d],advance_recovery=100,adjustment=200,retention_rate=10)
    assert p["retention"]==pytest.approx(120) and p["net_amount"]==pytest.approx(930)

def test_advance_and_site_material_balance():
    a=AdvancePayment("A1",500,125)
    s=SiteMaterial("S1","C","cement",100,30,"kg")
    assert a.outstanding==375 and s.balance==70

def test_fail_closed():
    with pytest.raises(ValueError): Deduction("","x",1)
    with pytest.raises(ValueError): AdjustmentRecord("A",1,100,0)
    with pytest.raises(ValueError): WorkOrder("W","title","2026","desc",-1)
