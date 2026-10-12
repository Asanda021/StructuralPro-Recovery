"""Fail-closed takeoff -> BOQ -> estimate acceptance path."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from core.takeoff.estimate import build_estimate
from core.pricing.iranian_price_data_production_pipeline_v1 import PriceRecord, select_effective_price

def accept_takeoff_to_estimate(takeoff_rows, prices: tuple[PriceRecord, ...], *,
                               as_of: date) -> dict:
    if not takeoff_rows:
        raise ValueError("takeoff_rows cannot be empty")
    if not prices:
        raise ValueError("price provenance is required")
    resolved = []
    for row in takeoff_rows:
        code = str(row.get("price_code") or row.get("item_code") or "").strip()
        if not code:
            raise ValueError("every takeoff row requires item_code/price_code")
        price = select_effective_price(prices, code, as_of)
        item = dict(row)
        item["price_code"] = code
        item["unit_price"] = float(price.rate)
        item["price_source_id"] = price.source_id
        item["price_source_version"] = price.source_version
        item["price_provenance_ref"] = price.provenance_ref
        resolved.append(item)
    estimate = build_estimate(resolved, aggregate=False)
    if not estimate["finalizable"]:
        raise ValueError("BOQ validation failed")
    return {"takeoff_rows": [dict(x) for x in takeoff_rows],
            "boq": estimate["boq"], "cost": estimate["cost"],
            "price_provenance": [{"price_code": x["price_code"],
                                  "source_id": x["price_source_id"],
                                  "source_version": x["price_source_version"],
                                  "provenance_ref": x["price_provenance_ref"]}
                                 for x in resolved],
            "finalizable": True}
