"""P58 — evidence-first real price/rate calibration contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class RateEvidence:
    item_code: str
    description: str
    unit: str
    rate: float
    currency: str
    source: str
    list_name: str
    version: str
    effective_date: str
    observed_at: str

@dataclass(frozen=True)
class CalibratedRate:
    item_code: str
    unit: str
    rate: float
    currency: str
    source: str
    version: str
    effective_date: str
    fingerprint: str

def validate_rates(rows: tuple[RateEvidence, ...]) -> None:
    if not rows:
        raise ValueError("price calibration requires explicit rate evidence")
    for row in rows:
        if not all((row.item_code.strip(), row.description.strip(), row.unit.strip(), row.currency.strip(), row.source.strip(), row.list_name.strip(), row.version.strip(), row.effective_date.strip(), row.observed_at.strip())):
            raise ValueError("incomplete rate evidence")
        if row.rate < 0:
            raise ValueError("rate cannot be negative")

def calibrate_rates(rows: tuple[RateEvidence, ...]) -> tuple[CalibratedRate, ...]:
    validate_rates(rows)
    by_key={}
    for row in rows:
        key=(row.item_code,row.unit,row.currency)
        prior=by_key.get(key)
        if prior is not None and prior.rate != row.rate:
            raise ValueError("conflicting rates for the same item/unit/currency")
        by_key[key]=row
    out=[]
    for key,row in sorted(by_key.items()):
        material=f"{row.item_code}|{row.unit}|{row.rate}|{row.currency}|{row.source}|{row.list_name}|{row.version}|{row.effective_date}|{row.observed_at}"
        out.append(CalibratedRate(row.item_code,row.unit,row.rate,row.currency,row.source,row.version,row.effective_date,sha256(material.encode()).hexdigest()))
    return tuple(out)
