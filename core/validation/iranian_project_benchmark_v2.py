from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkRow:
    item_id: str
    reference_quantity: float
    system_quantity: float


def compare(rows: list[BenchmarkRow]) -> dict:
    if not rows:
        raise ValueError("benchmark requires at least one reference row")
    errors = []
    for row in rows:
        if row.reference_quantity < 0 or row.system_quantity < 0:
            raise ValueError("quantities cannot be negative")
        if row.reference_quantity == 0:
            error = 0.0 if row.system_quantity == 0 else 1.0
        else:
            error = abs(row.system_quantity - row.reference_quantity) / row.reference_quantity
        errors.append(error)
    mean_error = sum(errors) / len(errors)
    pass_rate = sum(e <= 0.02 for e in errors) / len(errors)
    return {
        "rows": len(rows),
        "mean_relative_error": round(mean_error, 8),
        "within_2_percent_rate": round(pass_rate, 8),
        "green2": mean_error <= 0.02 and pass_rate >= 0.95,
    }
