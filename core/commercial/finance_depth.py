"""Deep project finance/payment controls for StructuralPro.

This module is intentionally UI-agnostic. It complements the existing commercial
ledger with payment allocation, budget variance, cash-flow planning and a
deterministic financial-control snapshot without changing legacy project data.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Iterable


PAYMENT_STATUSES = {"unallocated", "partial", "allocated", "cancelled"}


def _money(value: Any, label: str = "amount") -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return value


def _text(value: Any, label: str, required: bool = False) -> str:
    value = " ".join(str(value or "").strip().split())
    if required and not value:
        raise ValueError(f"{label} is required")
    return value


def _date_key(value: Any) -> str:
    raw = str(value or "").strip()
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    raw = raw.translate(trans).replace("-", "/").replace(".", "/")
    parts = raw.split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return "/".join(f"{int(part):04d}" if i == 0 else f"{int(part):02d}" for i, part in enumerate(parts))
    return raw


@dataclass(frozen=True)
class PaymentRecord:
    id: str
    amount: float
    date: str = ""
    reference: str = ""
    document_id: int | None = None
    commitment_id: int | None = None
    counterparty_id: str | None = None
    notes: str = ""
    status: str = "unallocated"


@dataclass(frozen=True)
class PaymentAllocation:
    id: str
    payment_id: str
    target_type: str
    target_id: int | str
    amount: float


@dataclass(frozen=True)
class BudgetLine:
    code: str
    category: str
    description: str
    planned: float


class FinancePaymentControl:
    """Deterministic payment, budget and cash-flow control over project data."""

    def __init__(
        self,
        *,
        payments: Iterable[PaymentRecord] = (),
        allocations: Iterable[PaymentAllocation] = (),
        budget: Iterable[BudgetLine] = (),
    ):
        self.payments = list(payments)
        self.allocations = list(allocations)
        self.budget = list(budget)
        self.validate()

    @staticmethod
    def _unique(items: Iterable[Any], label: str) -> set[str]:
        seen: set[str] = set()
        for item in items:
            key = str(item.id).strip()
            if not key:
                raise ValueError(f"{label} id is required")
            if key in seen:
                raise ValueError(f"duplicate {label} id: {key}")
            seen.add(key)
        return seen

    def validate(self) -> "FinancePaymentControl":
        payment_ids = self._unique(self.payments, "payment")
        self._unique(self.allocations, "allocation")
        budget_codes: set[str] = set()
        for budget in self.budget:
            code = _text(budget.code, "budget code", True)
            if code in budget_codes:
                raise ValueError(f"duplicate budget id: {code}")
            budget_codes.add(code)
        for p in self.payments:
            _money(p.amount, "payment amount")
            if p.status not in PAYMENT_STATUSES:
                raise ValueError(f"invalid payment status: {p.status}")
            if p.document_id is not None and int(p.document_id) <= 0:
                raise ValueError("document_id must be positive")
            if p.commitment_id is not None and int(p.commitment_id) <= 0:
                raise ValueError("commitment_id must be positive")
        for a in self.allocations:
            if a.payment_id not in payment_ids:
                raise ValueError(f"unknown payment: {a.payment_id}")
            if a.target_type not in {"document", "commitment"}:
                raise ValueError(f"invalid allocation target: {a.target_type}")
            if str(a.target_id).strip() == "":
                raise ValueError("allocation target_id is required")
            _money(a.amount, "allocation amount")
        for b in self.budget:
            _text(b.code, "budget code", True)
            _text(b.category, "budget category", True)
            _text(b.description, "budget description")
            _money(b.planned, "planned budget")
        self._validate_payment_totals()
        return self

    def _validate_payment_totals(self) -> None:
        by_payment: dict[str, float] = {}
        for a in self.allocations:
            by_payment[a.payment_id] = by_payment.get(a.payment_id, 0.0) + a.amount
        payments = {p.id: p for p in self.payments}
        for pid, allocated in by_payment.items():
            if allocated > payments[pid].amount + 1e-9:
                raise ValueError(f"payment over-allocated: {pid}")

    def add_payment(self, payment: PaymentRecord) -> PaymentRecord:
        self.payments.append(payment)
        try:
            self.validate()
        except Exception:
            self.payments.pop()
            raise
        return payment

    def allocate(self, allocation: PaymentAllocation) -> PaymentAllocation:
        if any(x.id == allocation.id for x in self.allocations):
            raise ValueError("duplicate allocation id")
        self.allocations.append(allocation)
        try:
            self.validate()
        except Exception:
            self.allocations.pop()
            raise
        return allocation

    def payment_status(self, payment_id: str) -> str:
        payment = next((x for x in self.payments if x.id == payment_id), None)
        if payment is None:
            raise KeyError(payment_id)
        allocated = sum(x.amount for x in self.allocations if x.payment_id == payment_id)
        if payment.status == "cancelled":
            return "cancelled"
        if allocated <= 0:
            return "unallocated"
        if allocated >= payment.amount:
            return "allocated"
        return "partial"

    def payment_summary(self) -> dict[str, Any]:
        rows = []
        for p in self.payments:
            allocated = sum(x.amount for x in self.allocations if x.payment_id == p.id)
            rows.append({
                **asdict(p),
                "allocated_amount": allocated,
                "unallocated_amount": max(p.amount - allocated, 0.0),
                "derived_status": self.payment_status(p.id),
            })
        return {
            "payment_count": len(rows),
            "payment_total": sum(x["amount"] for x in rows),
            "allocated_total": sum(x["allocated_amount"] for x in rows),
            "unallocated_total": sum(x["unallocated_amount"] for x in rows),
            "rows": rows,
        }

    def allocation_summary(self) -> dict[str, Any]:
        return {
            "allocation_count": len(self.allocations),
            "allocated_total": sum(x.amount for x in self.allocations),
            "rows": [asdict(x) for x in self.allocations],
        }

    def budget_control(self, *, actual_costs: Iterable[dict[str, Any]] = (),
                       commitments: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
        rows = []
        actual_by_category: dict[str, float] = {}
        committed_by_category: dict[str, float] = {}
        for x in actual_costs:
            category = _text(x.get("category", ""), "cost category") or "سایر"
            actual_by_category[category] = actual_by_category.get(category, 0.0) + _money(x.get("amount", 0), "cost amount")
        for x in commitments:
            category = _text(x.get("category", ""), "commitment category") or "سایر"
            committed_by_category[category] = committed_by_category.get(category, 0.0) + _money(x.get("amount", 0), "commitment amount")
        categories = {x.category for x in self.budget} | set(actual_by_category) | set(committed_by_category)
        for b in self.budget:
            # Multiple budget lines in one category are aggregated below.
            _ = b
        planned_by_category: dict[str, float] = {}
        for b in self.budget:
            planned_by_category[b.category] = planned_by_category.get(b.category, 0.0) + b.planned
        for category in sorted(categories):
            planned = planned_by_category.get(category, 0.0)
            committed = committed_by_category.get(category, 0.0)
            actual = actual_by_category.get(category, 0.0)
            rows.append({
                "category": category,
                "planned": planned,
                "committed": committed,
                "actual": actual,
                "committed_variance": planned - committed,
                "actual_variance": planned - actual,
                "committed_over_budget": committed > planned if planned else committed > 0,
                "actual_over_budget": actual > planned if planned else actual > 0,
            })
        return {
            "rows": rows,
            "planned_total": sum(x["planned"] for x in rows),
            "committed_total": sum(x["committed"] for x in rows),
            "actual_total": sum(x["actual"] for x in rows),
            "committed_variance": sum(x["committed_variance"] for x in rows),
            "actual_variance": sum(x["actual_variance"] for x in rows),
            "over_budget_categories": [x["category"] for x in rows if x["committed_over_budget"] or x["actual_over_budget"]],
        }

    def cash_flow(self, *, receipts: Iterable[dict[str, Any]] = (),
                  costs: Iterable[dict[str, Any]] = (),
                  payments: Iterable[dict[str, Any]] = (),
                  commitments: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
        buckets: dict[str, dict[str, float]] = {}

        def bucket(date: Any) -> dict[str, float]:
            key = _date_key(date) or "بدون تاریخ"
            return buckets.setdefault(key, {"cash_in": 0.0, "cash_out": 0.0, "committed_out": 0.0})

        for x in receipts:
            bucket(x.get("date"))["cash_in"] += _money(x.get("amount", 0), "receipt amount")
        for x in costs:
            bucket(x.get("date"))["cash_out"] += _money(x.get("amount", 0), "cost amount")
        for x in payments:
            bucket(x.get("date"))["cash_out"] += _money(x.get("amount", 0), "payment amount")
        for x in commitments:
            bucket(x.get("due_date") or x.get("date"))["committed_out"] += _money(x.get("amount", 0), "commitment amount")

        rows = []
        cumulative = 0.0
        for date in sorted(buckets):
            row = {"date": date, **buckets[date]}
            row["net_cash"] = row["cash_in"] - row["cash_out"]
            cumulative += row["net_cash"]
            row["cumulative_cash"] = cumulative
            rows.append(row)
        return {
            "rows": rows,
            "cash_in": sum(x["cash_in"] for x in rows),
            "cash_out": sum(x["cash_out"] for x in rows),
            "committed_out": sum(x["committed_out"] for x in rows),
            "net_cash": sum(x["net_cash"] for x in rows),
            "minimum_cumulative_cash": min((x["cumulative_cash"] for x in rows), default=0.0),
        }

    def control_snapshot(self, *, actual_costs: Iterable[dict[str, Any]] = (),
                         commitments: Iterable[dict[str, Any]] = (),
                         receipts: Iterable[dict[str, Any]] = (),
                         costs: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
        payments = [asdict(x) for x in self.payments]
        budget = self.budget_control(actual_costs=actual_costs, commitments=commitments)
        cash = self.cash_flow(receipts=receipts, costs=costs, payments=payments, commitments=commitments)
        payment = self.payment_summary()
        return {
            "payments": payment,
            "allocations": self.allocation_summary(),
            "budget": budget,
            "cash_flow": cash,
            "warnings": {
                "unallocated_payment": payment["unallocated_total"] > 0,
                "over_budget": bool(budget["over_budget_categories"]),
                "negative_cash": cash["minimum_cumulative_cash"] < 0,
            },
        }

    def export_dict(self) -> dict[str, Any]:
        return {
            "payments": [asdict(x) for x in self.payments],
            "allocations": [asdict(x) for x in self.allocations],
            "budget": [asdict(x) for x in self.budget],
        }
