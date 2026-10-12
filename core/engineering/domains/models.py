"""Common auditable quantity result for engineering domains."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class DomainQuantity:
    domain: str
    item: str
    quantity: float
    unit: str
    formula: str
    source_code: str = ""
    source_edition: str = ""
    warnings: tuple[str, ...] = ()

    def validate(self):
        if isinstance(self.quantity, bool) or not math.isfinite(float(self.quantity)) or self.quantity < 0:
            raise ValueError("quantity must be finite and non-negative")
        if not self.unit.strip(): raise ValueError("unit is required")
        if not self.formula.strip(): raise ValueError("formula is required")
        return self

def positive(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try: value=float(value)
    except (TypeError, ValueError, OverflowError) as exc: raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value

def count(value, name="count"):
    value=positive(value,name)
    if int(value)!=value: raise ValueError(f"{name} must be an integer")
    return int(value)
