"""P123 deterministic batch aggregation with bounded chunks."""
from __future__ import annotations

def chunked(items, chunk_size: int):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    items = list(items)
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]

def aggregate(rows: list[dict], chunk_size: int = 500) -> list[dict]:
    totals = {}
    for chunk in chunked(rows, chunk_size):
        for row in chunk:
            key = (str(row["trade"]), str(row["code"]), str(row["unit"]))
            qty = float(row["quantity"])
            if qty < 0:
                raise ValueError("quantity cannot be negative")
            totals[key] = totals.get(key, 0.0) + qty
    return [
        {"trade": t, "code": c, "unit": u, "quantity": q}
        for (t, c, u), q in sorted(totals.items())
    ]
