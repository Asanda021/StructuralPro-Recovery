"""Phase 17 commercial control: statements, contract progress, deductions and estimate-vs-actual.

UI-agnostic and deterministic. Monetary values are caller-supplied; no official
price or tax value is fabricated here. Percentages are represented as decimals.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
from typing import Any, Iterable

DEDUCTION_KINDS = {"retention", "advance_recovery", "tax", "insurance", "other"}

def _num(value: Any, label: str) -> float:
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return x

def _rate(value: Any, label: str) -> float:
    x = float(value)
    if not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError(f"{label} must be between 0 and 1")
    return x

@dataclass(frozen=True)
class CommercialItem:
    code: str
    description: str
    unit: str
    contract_quantity: float
    unit_price: float

@dataclass(frozen=True)
class Deduction:
    kind: str
    amount: float
    description: str = ""

class CommercialControl:
    """Single deterministic source for period statements and commercial KPIs."""

    def __init__(self, items: Iterable[CommercialItem], *, contract_id: str = "",
                 title: str = "", advance: float = 0.0):
        self.items = list(items)
        self.contract_id = str(contract_id).strip()
        self.title = str(title).strip()
        self.advance = _num(advance, "advance")
        self._validate_items()

    def _validate_items(self):
        seen = set()
        for item in self.items:
            code = str(item.code).strip()
            if not code or code in seen:
                raise ValueError(f"duplicate or missing item code: {code or '<empty>'}")
            seen.add(code)
            _num(item.contract_quantity, "contract quantity")
            _num(item.unit_price, "unit price")

    def contract_value(self) -> float:
        return round(sum(_num(x.contract_quantity, "contract quantity") *
                         _num(x.unit_price, "unit price") for x in self.items), 10)

    def build_statement(self, quantities: dict[str, float], previous: dict[str, float] | None = None,
                        deductions: Iterable[Deduction] = ()) -> dict[str, Any]:
        previous = previous or {}
        by_code = {x.code: x for x in self.items}
        if set(quantities) - set(by_code):
            raise ValueError("unknown statement item")
        rows = []
        for item in self.items:
            prev = _num(previous.get(item.code, 0), "previous quantity")
            current = _num(quantities.get(item.code, 0), "current quantity")
            contract = _num(item.contract_quantity, "contract quantity")
            if prev + current > contract + 1e-9:
                raise ValueError(f"progress exceeds contract for {item.code}")
            cumulative = prev + current
            rows.append({
                **asdict(item), "previous_quantity": prev, "current_quantity": current,
                "cumulative_quantity": cumulative,
                "remaining_quantity": contract - cumulative,
                "progress_percent": 0 if contract == 0 else cumulative / contract * 100,
                "previous_amount": round(prev * item.unit_price, 10),
                "current_amount": round(current * item.unit_price, 10),
                "cumulative_amount": round(cumulative * item.unit_price, 10),
            })
        gross = round(sum(x["current_amount"] for x in rows), 10)
        cumulative = round(sum(x["cumulative_amount"] for x in rows), 10)
        ds = []
        for d in deductions:
            kind = str(d.kind).strip()
            if kind not in DEDUCTION_KINDS:
                raise ValueError(f"invalid deduction kind: {kind}")
            amount = _num(d.amount, "deduction amount")
            if amount > gross + 1e-9:
                raise ValueError("deductions cannot exceed current gross")
            ds.append({**asdict(d), "amount": round(amount, 10)})
        deduction_total = round(sum(x["amount"] for x in ds), 10)
        return {
            "contract_id": self.contract_id, "title": self.title,
            "contract_value": self.contract_value(), "lines": rows,
            "gross_current": gross, "cumulative_value": cumulative,
            "deductions": ds, "deduction_total": deduction_total,
            "net_current": round(gross - deduction_total, 10),
            "remaining_value": round(max(self.contract_value() - cumulative, 0), 10),
            "progress_percent": 0 if self.contract_value() == 0 else cumulative / self.contract_value() * 100,
        }

    def contract_status(self, cumulative_value: float, *, paid: float = 0,
                        current_commitments: float = 0) -> dict[str, Any]:
        total = self.contract_value()
        cumulative = _num(cumulative_value, "cumulative value")
        paid = _num(paid, "paid")
        commitments = _num(current_commitments, "current commitments")
        return {
            "contract_id": self.contract_id, "contract_value": total,
            "performed_value": min(cumulative, total),
            "remaining_value": max(total - cumulative, 0),
            "progress_percent": 0 if total == 0 else min(cumulative / total * 100, 100),
            "paid": paid, "unpaid_performed": max(cumulative - paid, 0),
            "commitments": commitments,
            "headroom": max(total - cumulative - commitments, 0),
            "over_contract": cumulative > total,
            "payment_ratio_percent": 0 if cumulative == 0 else min(paid / cumulative * 100, 100),
        }

    @staticmethod
    def estimate_vs_actual(estimate: Iterable[dict[str, Any]],
                           actual: Iterable[dict[str, Any]]) -> dict[str, Any]:
        def aggregate(rows, amount_key):
            out = {}
            for row in rows:
                code = str(row.get("code") or row.get("price_code") or row.get("category") or "").strip()
                if not code:
                    raise ValueError("estimate/actual row requires code")
                amount = _num(row.get(amount_key, row.get("amount", 0)), amount_key)
                out[code] = out.get(code, 0.0) + amount
            return out
        planned = aggregate(estimate, "estimated_amount")
        spent = aggregate(actual, "actual_amount")
        codes = sorted(set(planned) | set(spent))
        rows = []
        for code in codes:
            e, a = planned.get(code, 0.0), spent.get(code, 0.0)
            rows.append({"code": code, "estimated": e, "actual": a,
                         "variance": round(e - a, 10),
                         "variance_percent": 0 if e == 0 else round((e - a) / e * 100, 10),
                         "over_budget": a > e})
        return {"rows": rows, "estimated_total": sum(x["estimated"] for x in rows),
                "actual_total": sum(x["actual"] for x in rows),
                "variance_total": sum(x["variance"] for x in rows),
                "over_budget_codes": [x["code"] for x in rows if x["over_budget"]]}

    @staticmethod
    def financial_report(statements: Iterable[dict[str, Any]]) -> dict[str, Any]:
        rows = list(statements)
        gross = sum(_num(x.get("gross_current", 0), "gross_current") for x in rows)
        deductions = sum(_num(x.get("deduction_total", 0), "deduction_total") for x in rows)
        net = sum(_num(x.get("net_current", 0), "net_current") for x in rows)
        return {"statement_count": len(rows), "gross_total": gross,
                "deduction_total": deductions, "net_total": net,
                "average_progress_percent": (sum(float(x.get("progress_percent", 0)) for x in rows) / len(rows)) if rows else 0}

    def export_dict(self) -> dict[str, Any]:
        return {"contract_id": self.contract_id, "title": self.title,
                "advance": self.advance, "items": [asdict(x) for x in self.items]}
