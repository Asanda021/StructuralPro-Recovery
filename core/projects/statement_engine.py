"""Validated construction progress and payment-statement engine."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Any
import math

def _finite_nonnegative(value: float, label: str) -> float:
    value=float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return value

def _rate(value: float, label: str) -> float:
    value=float(value)
    if not math.isfinite(value) or value < 0 or value > 1:
        raise ValueError(f"{label} must be between 0 and 1")
    return value

@dataclass(frozen=True)
class StatementLine:
    code: str; description: str; unit: str; contract_quantity: float
    unit_price: float; current_quantity: float; previous_quantity: float=0.0
    def validated(self):
        cq=_finite_nonnegative(self.contract_quantity,"contract_quantity")
        up=_finite_nonnegative(self.unit_price,"unit_price")
        cur=_finite_nonnegative(self.current_quantity,"current_quantity")
        prev=_finite_nonnegative(self.previous_quantity,"previous_quantity")
        if prev > cq:
            raise ValueError(f"previous quantity exceeds contract for {self.code}")
        if cur > max(cq-prev,0):
            raise ValueError(f"current quantity exceeds remaining contract for {self.code}")
        if not str(self.code).strip(): raise ValueError("statement line code is required")
        if not str(self.unit).strip(): raise ValueError("statement line unit is required")
        return self
    def amount_current(self): return self.validated().current_quantity*self.unit_price
    def amount_cumulative(self): return self.validated().previous_quantity*self.unit_price+self.current_quantity*self.unit_price

def build_statement(lines: Iterable[StatementLine], *, retention_rate=0.0,
                    advance_recovery_rate=0.0, other_deduction_rate=0.0,
                    advance_paid=0.0) -> dict[str,Any]:
    rows=[]; gross_current=gross_cumulative=0.0; seen=set()
    retention_rate=_rate(retention_rate,"retention_rate")
    advance_recovery_rate=_rate(advance_recovery_rate,"advance_recovery_rate")
    other_deduction_rate=_rate(other_deduction_rate,"other_deduction_rate")
    advance_paid=_finite_nonnegative(advance_paid,"advance_paid")
    for x in lines:
        x.validated()
        if x.code in seen: raise ValueError(f"duplicate statement line: {x.code}")
        seen.add(x.code)
        cur=x.amount_current(); cum=x.amount_cumulative()
        rows.append({**asdict(x),"current_amount":cur,"cumulative_amount":cum,
                     "remaining_quantity":x.contract_quantity-x.previous_quantity-x.current_quantity,
                     "progress_percent":0 if x.contract_quantity==0 else
                         (x.previous_quantity+x.current_quantity)/x.contract_quantity*100})
        gross_current+=cur; gross_cumulative+=cum
    retention=gross_current*retention_rate
    advance_recovery=min(gross_current*advance_recovery_rate,advance_paid)
    other=gross_current*other_deduction_rate
    return {"lines":rows,"gross_current":gross_current,"gross_cumulative":gross_cumulative,
            "retention":retention,"advance_recovery":advance_recovery,"other_deductions":other,
            "deductions_total":retention+advance_recovery+other,
            "payable":gross_current-retention-advance_recovery-other}
