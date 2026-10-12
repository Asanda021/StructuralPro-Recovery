"""Phase 17 acceptance tests: commercial statement and cost-control parity."""
import pytest
from core.commercial.phase17 import CommercialControl, CommercialItem, Deduction

def _control():
    return CommercialControl([
        CommercialItem("A","Concrete","m3",100,1000),
        CommercialItem("B","Rebar","kg",1000,20),
    ], contract_id="C17", title="Project")

def test_statement_previous_current_cumulative_and_deductions():
    c=_control()
    s=c.build_statement({"A":10,"B":100},{"A":20,"B":200},
                        [Deduction("retention",100),Deduction("tax",50)])
    a=next(x for x in s["lines"] if x["code"]=="A")
    assert (a["previous_quantity"],a["current_quantity"],a["cumulative_quantity"])==(20,10,30)
    assert s["gross_current"]==12000
    assert s["deduction_total"]==150
    assert s["net_current"]==11850

def test_statement_rejects_contract_overrun_and_unknown_item():
    c=_control()
    with pytest.raises(ValueError): c.build_statement({"A":90},{"A":20})
    with pytest.raises(ValueError): c.build_statement({"X":1})

def test_contract_status_and_payment_control():
    c=_control()
    s=c.contract_status(30000, paid=12000, current_commitments=5000)
    assert s["performed_value"]==30000
    assert s["unpaid_performed"]==18000
    assert s["progress_percent"]==25.0
    assert s["headroom"]==85000

def test_estimate_vs_actual_is_deterministic():
    r=CommercialControl.estimate_vs_actual(
        [{"code":"A","estimated_amount":1000},{"code":"B","estimated_amount":500}],
        [{"code":"A","actual_amount":1200},{"code":"B","actual_amount":300},{"code":"C","actual_amount":50}],
    )
    assert r["estimated_total"]==1500
    assert r["actual_total"]==1550
    assert r["variance_total"]==-50
    assert r["over_budget_codes"]==["A","C"]

def test_financial_report_aggregates_periods():
    r=CommercialControl.financial_report([
        {"gross_current":100,"deduction_total":10,"net_current":90,"progress_percent":10},
        {"gross_current":200,"deduction_total":20,"net_current":180,"progress_percent":30},
    ])
    assert r=={"statement_count":2,"gross_total":300,"deduction_total":30,"net_total":270,"average_progress_percent":20.0}
