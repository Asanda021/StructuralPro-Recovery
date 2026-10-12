"""P121 multi-trade quantity/takeoff boundary: deterministic, deduplicated, trade-aware."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TradeQuantity:
    element_id: str
    trade: str
    code: str
    quantity: float
    unit: str
    source: str = "takeoff"

    def __post_init__(self):
        if not self.element_id or not self.trade or not self.code or not self.unit:
            raise ValueError("trade quantity identity fields are required")
        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")

def normalize(items: list[TradeQuantity]) -> list[TradeQuantity]:
    out = {}
    for item in items:
        key = (item.element_id, item.trade.casefold(), item.code.casefold(), item.unit.casefold())
        if key in out:
            prev = out[key]
            out[key] = TradeQuantity(prev.element_id, prev.trade, prev.code,
                                     prev.quantity + item.quantity, prev.unit, prev.source)
        else:
            out[key] = item
    return sorted(out.values(), key=lambda x: (x.trade.casefold(), x.code.casefold(), x.element_id))

def summarize(items: list[TradeQuantity]) -> dict:
    rows = normalize(items)
    totals = {}
    for row in rows:
        key = (row.trade, row.code, row.unit)
        totals[key] = totals.get(key, 0.0) + row.quantity
    return {"rows": rows, "totals": [
        {"trade": t, "code": c, "unit": u, "quantity": q}
        for (t, c, u), q in sorted(totals.items())
    ]}
