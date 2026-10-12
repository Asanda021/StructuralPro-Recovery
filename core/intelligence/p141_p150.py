"""P141-P150 global rules and cost-intelligence primitives.

Deterministic domain layer. It does not invent market prices or exchange rates.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from statistics import mean
from typing import Iterable

SUPPORTED_LANGUAGES = {"fa", "en", "ar", "zh"}
SUPPORTED_CURRENCIES = {"IRR", "USD", "EUR", "AED", "TRY", "GBP"}
SUPPORTED_REGIONS = {"IR", "TR", "AE", "EU", "US", "GLOBAL"}

@dataclass(frozen=True)
class RegionalRule:
    region: str
    language: str
    currency: str
    tax_rate: float = 0.0
    escalation_rate: float = 0.0

@dataclass(frozen=True)
class PricePoint:
    item: str
    unit: str
    currency: str
    price: float
    source: str
    period: str

@dataclass(frozen=True)
class HistoricalObservation:
    period: str
    total_cost: float
    quantity: float

@dataclass(frozen=True)
class RiskSignal:
    code: str
    severity: str
    message: str

def validate_regional_rule(rule: RegionalRule) -> RegionalRule:
    if rule.region not in SUPPORTED_REGIONS: raise ValueError("unsupported region")
    if rule.language not in SUPPORTED_LANGUAGES: raise ValueError("unsupported language")
    if rule.currency not in SUPPORTED_CURRENCIES: raise ValueError("unsupported currency")
    if not 0 <= rule.tax_rate <= 1: raise ValueError("tax_rate must be between 0 and 1")
    if rule.escalation_rate < -1: raise ValueError("escalation_rate is invalid")
    return rule

def map_standard(standard: str, region: str) -> dict:
    if not standard.strip() or region not in SUPPORTED_REGIONS:
        raise ValueError("standard and supported region are required")
    return {"standard": standard.strip(), "region": region, "mapped": True}

def normalize_pricebook(points: Iterable[PricePoint]) -> list[PricePoint]:
    out = []
    for p in points:
        if p.currency not in SUPPORTED_CURRENCIES or p.price < 0:
            raise ValueError("invalid price point")
        if not p.item.strip() or not p.unit.strip() or not p.source.strip() or not p.period.strip():
            raise ValueError("price point identity is incomplete")
        out.append(p)
    return sorted(out, key=lambda x: (x.item, x.unit, x.currency, x.period, x.source))

def cost_forecast(history: Iterable[HistoricalObservation], periods: int = 1) -> float:
    rows = list(history)
    if not rows or periods < 1: raise ValueError("history and positive periods are required")
    if any(r.total_cost < 0 or r.quantity <= 0 for r in rows): raise ValueError("invalid history")
    unit_costs = [r.total_cost / r.quantity for r in rows]
    return mean(unit_costs) * periods

def cost_risk(points: Iterable[PricePoint], threshold: float = 0.15) -> list[RiskSignal]:
    rows = list(points)
    signals = []
    by_item = {}
    for p in rows: by_item.setdefault(p.item, []).append(p)
    for item, vals in by_item.items():
        if len(vals) > 1:
            avg = mean(v.price for v in vals)
            if avg and (max(v.price for v in vals)-min(v.price for v in vals))/avg > threshold:
                signals.append(RiskSignal("P150-PRICE-VARIANCE", "warning", f"High price variance for '{item}'."))
    return signals

def deterministic_intelligence_digest(rule: RegionalRule, points: Iterable[PricePoint]) -> str:
    validate_regional_rule(rule)
    payload = {"rule": rule.__dict__, "prices": [p.__dict__ for p in normalize_pricebook(points)]}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
