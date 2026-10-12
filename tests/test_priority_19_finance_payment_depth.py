"""Regression coverage for Priority 19 finance/payment depth."""
import pytest

from core.commercial.finance_depth import (
    FinancePaymentControl,
    PaymentAllocation,
    PaymentRecord,
    BudgetLine,
)


def test_payment_allocation_status_and_overallocation():
    control = FinancePaymentControl(
        payments=[PaymentRecord("P1", 1000)],
        allocations=[],
    )
    control.allocate(PaymentAllocation("A1", "P1", "document", 1, 600))
    assert control.payment_status("P1") == "partial"
    assert control.payment_summary()["unallocated_total"] == 400

    with pytest.raises(ValueError):
        control.allocate(PaymentAllocation("A2", "P1", "document", 1, 401))


def test_budget_control_tracks_planned_committed_actual_variance():
    control = FinancePaymentControl(
        budget=[
            BudgetLine("B1", "مصالح", "خرید مصالح", 1000),
            BudgetLine("B2", "دستمزد", "نیروی اجرا", 500),
        ]
    )
    result = control.budget_control(
        actual_costs=[
            {"category": "مصالح", "amount": 800},
            {"category": "دستمزد", "amount": 550},
        ],
        commitments=[
            {"category": "مصالح", "amount": 1100},
        ],
    )
    materials = next(x for x in result["rows"] if x["category"] == "مصالح")
    labor = next(x for x in result["rows"] if x["category"] == "دستمزد")
    assert materials["committed_variance"] == -100
    assert materials["actual_variance"] == 200
    assert labor["actual_over_budget"] is True
    assert result["over_budget_categories"] == ["دستمزد", "مصالح"]


def test_cash_flow_has_cumulative_balance_and_committed_outflow():
    control = FinancePaymentControl(
        payments=[PaymentRecord("P1", 300, date="1405/02/10")]
    )
    result = control.cash_flow(
        receipts=[{"date": "1405/02/01", "amount": 1000}],
        costs=[{"date": "1405/02/05", "amount": 200}],
        payments=[{"date": "1405/02/10", "amount": 300}],
        commitments=[{"date": "1405/02/15", "due_date": "1405/02/20", "amount": 700}],
    )
    assert result["cash_in"] == 1000
    assert result["cash_out"] == 500
    assert result["committed_out"] == 700
    assert result["net_cash"] == 500
    assert result["minimum_cumulative_cash"] == 500
    assert result["rows"][-1]["date"] == "1405/02/20"


def test_application_payment_budget_and_snapshot(tmp_path):
    from core.platform.application import StructuralProApp

    app = StructuralProApp(tmp_path)
    app.create_project("کنترل مالی عمیق", "P19")
    cp = app.add_project_counterparty("P19", "پیمانکار")
    commitment = app.add_project_commitment(
        "P19", 1000, category="مصالح", due_date="1405/03/10", counterparty=cp["name"]
    )
    payment = app.add_project_payment(
        "P19", 600, date="1405/03/05", reference="PAY-1",
        commitment_id=commitment["id"], counterparty_id=cp["id"],
    )
    allocation = app.allocate_project_payment(
        "P19", payment["id"], "commitment", commitment["id"], 600
    )
    assert allocation["amount"] == 600
    assert app.project_payment_summary("P19")["unallocated_total"] == 0

    app.add_project_cost("P19", "مصالح", 700, date="1405/03/04", counterparty=cp["name"])
    app.add_financial_budget_line("P19", "B1", "مصالح", 800, description="بودجه خرید")
    budget = app.project_budget_control("P19")
    assert budget["actual_total"] == 700
    assert budget["committed_total"] == 1000
    assert budget["over_budget_categories"] == ["مصالح"]

    cash = app.project_cash_flow_control("P19")
    assert cash["cash_in"] == 0
    assert cash["cash_out"] == 1300
    assert cash["committed_out"] == 1000

    snapshot = app.project_finance_payment_depth_snapshot("P19")
    assert snapshot["warnings"]["unallocated_payment"] is False
    assert snapshot["warnings"]["over_budget"] is True
    assert snapshot["payments"]["payment_count"] == 1

    out = tmp_path / "finance-depth.csv"
    assert app.project_finance_payment_depth_report("P19", "csv", out) == out
    assert out.exists() and out.stat().st_size > 0


def test_application_rejects_invalid_payment_links_and_duplicate_budget(tmp_path):
    from core.platform.application import StructuralProApp

    app = StructuralProApp(tmp_path)
    app.create_project("کنترل اعتبار", "P19B")
    with pytest.raises(KeyError):
        app.add_project_payment("P19B", 100, commitment_id=99)

    app.add_financial_budget_line("P19B", "B1", "سایر", 100)
    with pytest.raises(ValueError):
        app.add_financial_budget_line("P19B", "B1", "سایر", 200)


def test_control_rejects_duplicate_and_unknown_allocation():
    with pytest.raises(ValueError):
        FinancePaymentControl(
            payments=[PaymentRecord("P1", 100)],
            allocations=[
                PaymentAllocation("A1", "P1", "document", 1, 50),
                PaymentAllocation("A1", "P1", "document", 1, 10),
            ],
        )
    with pytest.raises(ValueError):
        FinancePaymentControl(
            payments=[PaymentRecord("P1", 100)],
            allocations=[PaymentAllocation("A1", "P2", "document", 1, 10)],
        )
