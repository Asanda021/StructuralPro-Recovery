import pytest
from core.commercial.finance_depth import FinancePaymentControl, PaymentAllocation, PaymentRecord, BudgetLine

def test_phase10_payment_allocation_and_budget_variance():
    control = FinancePaymentControl(
        payments=[PaymentRecord("PAY-1", 1000)],
        budget=[BudgetLine("B-1", "مصالح", "مصالح پروژه", 900)],
    )
    control.allocate(PaymentAllocation("ALLOC-1", "PAY-1", "document", 1, 600))
    assert control.payment_status("PAY-1") == "partial"
    assert control.payment_summary()["unallocated_total"] == 400
    with pytest.raises(ValueError):
        control.allocate(PaymentAllocation("ALLOC-2", "PAY-1", "document", 2, 401))
    result = control.budget_control(
        actual_costs=[{"category": "مصالح", "amount": 950}],
        commitments=[{"category": "مصالح", "amount": 800}],
    )
    materials = next(row for row in result["rows"] if row["category"] == "مصالح")
    assert materials["actual_over_budget"] is True
    assert materials["committed_variance"] == 100
