"""P43 — evidence-first Estimate & Cost Engine 2.0.

Converts accepted quantities into transparent material/labor/machinery/other
costs using caller-supplied rates. No hidden conversion, escalation, tax,
contingency, currency conversion or invented rate is applied.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable


_COST_TYPES = {"material", "labor", "machinery", "other"}


def _text(*values: str) -> None:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("cost identity/provenance is incomplete")


def _money(value: Decimal, label: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{label} must be a finite non-negative Decimal")


@dataclass(frozen=True)
class EstimateLine:
    line_id: str
    item_code: str
    description: str
    category: str
    unit: str
    quantity: Decimal
    source_id: str

    def validate(self) -> None:
        _text(self.line_id, self.item_code, self.description, self.category, self.unit, self.source_id)
        if self.category not in _COST_TYPES:
            raise ValueError("invalid estimate category")
        _money(self.quantity, "quantity")


@dataclass(frozen=True)
class CostRate:
    item_code: str
    category: str
    unit: str
    rate: Decimal
    currency: str
    source_id: str
    source_version: str
    provenance_ref: str

    def validate(self) -> None:
        _text(self.item_code, self.category, self.unit, self.currency,
              self.source_id, self.source_version, self.provenance_ref)
        if self.category not in _COST_TYPES:
            raise ValueError("invalid rate category")
        _money(self.rate, "rate")


@dataclass(frozen=True)
class EstimateResult:
    scenario: str
    currency: str
    lines: tuple[dict[str, object], ...]
    breakdown: dict[str, Decimal]
    grand_total: Decimal
    fingerprint: str


def build_estimate(
    lines: Iterable[EstimateLine],
    rates: Iterable[CostRate],
    *,
    scenario: str,
) -> EstimateResult:
    """Price accepted quantity lines against exact unit/category rates.

    Currency compatibility is evaluated only against rates actually used by
    BOQ lines. Unused catalog rates do not change the currency of an estimate.
    """
    _text(scenario)
    boq = tuple(lines)
    price = tuple(rates)
    if not boq:
        raise ValueError("at least one estimate line is required")

    seen_lines: set[str] = set()
    rate_by_key: dict[tuple[str, str, str], CostRate] = {}

    for line in boq:
        line.validate()
        if line.line_id in seen_lines:
            raise ValueError(f"duplicate estimate line id: {line.line_id}")
        seen_lines.add(line.line_id)

    for rate in price:
        rate.validate()
        key = (rate.item_code, rate.category, rate.unit)
        if key in rate_by_key:
            raise ValueError(f"duplicate rate key: {key}")
        rate_by_key[key] = rate

    used_rates: list[CostRate] = []
    for line in boq:
        rate = rate_by_key.get((line.item_code, line.category, line.unit))
        if rate is None:
            raise LookupError(
                f"no supplied rate for {line.item_code}/{line.category}/{line.unit}"
            )
        used_rates.append(rate)

    currencies = {rate.currency for rate in used_rates}
    if len(currencies) != 1:
        raise ValueError("exactly one currency is required for an estimate")
    currency = next(iter(currencies))

    breakdown = {category: Decimal("0") for category in sorted(_COST_TYPES)}
    result_lines: list[dict[str, object]] = []
    for line, rate in zip(boq, used_rates):
        amount = line.quantity * rate.rate
        if not amount.is_finite():
            raise ValueError(f"estimate amount is not finite for line: {line.line_id}")
        result_lines.append({
            "line_id": line.line_id,
            "item_code": line.item_code,
            "description": line.description,
            "category": line.category,
            "unit": line.unit,
            "quantity": line.quantity,
            "rate": rate.rate,
            "amount": amount,
            "currency": rate.currency,
            "quantity_source_id": line.source_id,
            "rate_source_id": rate.source_id,
            "rate_source_version": rate.source_version,
            "rate_provenance_ref": rate.provenance_ref,
        })
        breakdown[line.category] += amount
        if not breakdown[line.category].is_finite():
            raise ValueError(f"estimate category total is not finite: {line.category}")

    grand_total = sum(breakdown.values(), Decimal("0"))
    if not grand_total.is_finite():
        raise ValueError("estimate grand total is not finite")
    fingerprint = _fingerprint(scenario, currency, result_lines, breakdown)
    return EstimateResult(
        scenario=scenario,
        currency=currency,
        lines=tuple(result_lines),
        breakdown=breakdown,
        grand_total=grand_total,
        fingerprint=fingerprint,
    )


def compare_scenarios(*estimates: EstimateResult) -> dict[str, object]:
    """Compare explicit scenarios; no winner or recommendation is inferred."""
    if not estimates:
        raise ValueError("at least one estimate is required")
    currencies = {x.currency for x in estimates}
    if len(currencies) != 1:
        raise ValueError("scenario currencies must match")
    return {
        "currency": estimates[0].currency,
        "scenarios": [
            {
                "scenario": x.scenario,
                "grand_total": x.grand_total,
                "breakdown": dict(x.breakdown),
                "fingerprint": x.fingerprint,
            }
            for x in estimates
        ],
    }


def _fingerprint(
    scenario: str,
    currency: str,
    lines: list[dict[str, object]],
    breakdown: dict[str, Decimal],
) -> str:
    def normalize(value: object) -> object:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, tuple):
            return [normalize(x) for x in value]
        if isinstance(value, list):
            return [normalize(x) for x in value]
        if isinstance(value, dict):
            return {str(k): normalize(v) for k, v in value.items()}
        return value

    payload = normalize({
        "scenario": scenario,
        "currency": currency,
        "lines": lines,
        "breakdown": breakdown,
    })
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
