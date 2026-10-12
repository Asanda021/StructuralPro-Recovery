"""Evidence-first BOQ -> estimate -> cost-control boundary.

Only caller-supplied quantities and price records are accepted. The module
performs transparent arithmetic and fails closed on missing identity,
incompatible units/currencies, duplicate lines, or invalid numeric values.
No quantity, price, currency conversion, escalation, contingency, or tax is
invented implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from typing import Iterable


@dataclass(frozen=True)
class BOQLine:
    line_id: str
    item_code: str
    description: str
    unit: str
    quantity: Decimal
    source_id: str
    revision: str


@dataclass(frozen=True)
class RateLine:
    item_code: str
    unit: str
    rate: Decimal
    currency: str
    source_id: str
    source_version: str
    provenance_ref: str


@dataclass(frozen=True)
class EstimateLine:
    line_id: str
    item_code: str
    quantity: Decimal
    unit: str
    rate: Decimal
    currency: str
    amount: Decimal
    boq_source_id: str
    price_source_id: str


@dataclass(frozen=True)
class CostEntry:
    entry_id: str
    line_id: str
    amount: Decimal
    currency: str
    source_id: str


@dataclass(frozen=True)
class CostControlResult:
    committed: Decimal
    actual: Decimal
    remaining: Decimal
    currency: str


def _required_text(*values: str) -> None:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("Required identity/provenance text is missing")


def _money(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{label} must be a finite non-negative Decimal")


def validate_boq_line(line: BOQLine) -> None:
    _required_text(line.line_id, line.item_code, line.description, line.unit,
                   line.source_id, line.revision)
    _money(line.quantity, "quantity")


def validate_rate_line(rate: RateLine) -> None:
    _required_text(rate.item_code, rate.unit, rate.currency, rate.source_id,
                   rate.source_version, rate.provenance_ref)
    _money(rate.rate, "rate")


def build_estimate(
    boq_lines: Iterable[BOQLine],
    rates: Iterable[RateLine],
) -> tuple[EstimateLine, ...]:
    """Price explicit BOQ lines using an explicit same-unit/same-currency rate."""
    boq = tuple(boq_lines)
    price = tuple(rates)
    seen: set[str] = set()
    rate_by_code: dict[str, RateLine] = {}
    for line in boq:
        validate_boq_line(line)
        if line.line_id in seen:
            raise ValueError(f"Duplicate BOQ line id: {line.line_id}")
        seen.add(line.line_id)
    for rate in price:
        validate_rate_line(rate)
        if rate.item_code in rate_by_code:
            raise ValueError(f"Duplicate price item code: {rate.item_code}")
        rate_by_code[rate.item_code] = rate

    result: list[EstimateLine] = []
    for line in boq:
        rate = rate_by_code.get(line.item_code)
        if rate is None:
            raise LookupError(f"No supplied price for item code: {line.item_code}")
        if line.unit != rate.unit:
            raise ValueError(f"Unit mismatch for item code: {line.item_code}")
        result.append(EstimateLine(
            line_id=line.line_id,
            item_code=line.item_code,
            quantity=line.quantity,
            unit=line.unit,
            rate=rate.rate,
            currency=rate.currency,
            amount=line.quantity * rate.rate,
            boq_source_id=line.source_id,
            price_source_id=rate.source_id,
        ))
    return tuple(result)


def total_estimate(lines: Iterable[EstimateLine], currency: str) -> Decimal:
    lines = tuple(lines)
    if not currency.strip():
        raise ValueError("currency is required")
    for line in lines:
        _required_text(line.line_id, line.item_code, line.unit, line.currency,
                       line.boq_source_id, line.price_source_id)
        _money(line.quantity, "quantity")
        _money(line.rate, "rate")
        _money(line.amount, "amount")
        if line.currency != currency:
            raise ValueError("Mixed currencies require explicit caller handling")
    return sum((line.amount for line in lines), Decimal("0"))


def control_costs(
    committed: Decimal,
    actual_entries: Iterable[CostEntry],
    currency: str,
) -> CostControlResult:
    """Compare explicit committed estimate against explicit actual entries."""
    _money(committed, "committed")
    if not currency.strip():
        raise ValueError("currency is required")
    entries = tuple(actual_entries)
    seen: set[str] = set()
    actual = Decimal("0")
    for entry in entries:
        _required_text(entry.entry_id, entry.line_id, entry.currency, entry.source_id)
        _money(entry.amount, "actual amount")
        if entry.entry_id in seen:
            raise ValueError(f"Duplicate cost entry id: {entry.entry_id}")
        seen.add(entry.entry_id)
        if entry.currency != currency:
            raise ValueError("Mixed currencies require explicit caller handling")
        actual += entry.amount
    return CostControlResult(
        committed=committed,
        actual=actual,
        remaining=committed - actual,
        currency=currency,
    )


def estimate_fingerprint(lines: Iterable[EstimateLine]) -> str:
    payload = []
    for line in lines:
        payload.append({
            "line_id": line.line_id,
            "item_code": line.item_code,
            "quantity": str(line.quantity),
            "unit": line.unit,
            "rate": str(line.rate),
            "currency": line.currency,
            "amount": str(line.amount),
            "boq_source_id": line.boq_source_id,
            "price_source_id": line.price_source_id,
        })
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
