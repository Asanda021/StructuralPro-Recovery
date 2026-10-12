"""Evidence-first Iranian price data production boundary.

Prices are imported as externally sourced facts. This module never fabricates
rates, dates, units, currencies, or escalation factors. Every price record
must carry source and validity provenance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from decimal import Decimal, InvalidOperation


SUPPORTED_CURRENCIES = frozenset({"IRR", "IRT"})


@dataclass(frozen=True)
class PriceRecord:
    item_code: str
    description: str
    unit: str
    rate: Decimal
    currency: str
    effective_date: date
    source_id: str
    source_version: str
    provenance_ref: str


def validate_price(record: PriceRecord) -> None:
    fields = (
        record.item_code,
        record.description,
        record.unit,
        record.currency,
        record.source_id,
        record.source_version,
        record.provenance_ref,
    )
    if any(not isinstance(value, str) or not value.strip() for value in fields):
        raise ValueError("Price identity and provenance fields are required")
    if record.currency not in SUPPORTED_CURRENCIES:
        raise ValueError("Unsupported currency")
    if not isinstance(record.rate, Decimal) or not record.rate.is_finite():
        raise ValueError("Rate must be a finite Decimal")
    if record.rate < 0:
        raise ValueError("Rate cannot be negative")
    if not isinstance(record.effective_date, date):
        raise ValueError("effective_date must be a date")


def canonical_price(record: PriceRecord) -> str:
    validate_price(record)
    payload = asdict(record)
    payload["rate"] = str(record.rate)
    payload["effective_date"] = record.effective_date.isoformat()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def price_fingerprint(record: PriceRecord) -> str:
    return hashlib.sha256(canonical_price(record).encode("utf-8")).hexdigest()


def parse_rate(value: str) -> Decimal:
    """Parse a supplied rate without applying hidden conversion."""
    try:
        rate = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid supplied price rate") from None
    if not rate.is_finite() or rate < 0:
        raise ValueError("Price rate must be finite and non-negative")
    return rate


def validate_catalog(records: tuple[PriceRecord, ...]) -> None:
    seen: set[str] = set()
    for record in records:
        validate_price(record)
        key = (record.item_code, record.effective_date)
        if key in seen:
            raise ValueError(
                f"Duplicate item code/effective date: {record.item_code}/{record.effective_date}"
            )
        seen.add(key)


def select_effective_price(
    records: tuple[PriceRecord, ...],
    item_code: str,
    as_of: date,
) -> PriceRecord:
    """Select the latest supplied price effective on/before a target date."""
    if not item_code.strip():
        raise ValueError("item_code is required")
    if not isinstance(as_of, date):
        raise ValueError("as_of must be a date")
    validate_catalog(records)
    candidates = [
        record
        for record in records
        if record.item_code == item_code and record.effective_date <= as_of
    ]
    if not candidates:
        raise LookupError("No effective price with supplied provenance")
    return max(candidates, key=lambda record: record.effective_date)
