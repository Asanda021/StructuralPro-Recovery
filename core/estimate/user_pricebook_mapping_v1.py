"""P83 — isolated user pricebook mapping bridge.

Builds candidates only from one validated year/discipline and prefers item-code
identity before description similarity. No cross-discipline/year pricing is allowed.
"""
from core.estimate.pricebook_mapping_v2 import map_items, mapping_gate

def candidates_for(rows, year, discipline):
    selected=[r for r in rows if r.year==year and r.discipline==discipline and r.unit_price is not None]
    if not selected:
        raise ValueError("no priced rows for requested year/discipline")
    return [{"item_code":r.item_code,"description":r.description,"unit":r.unit} for r in selected]

def map_user_takeoff(takeoff_rows, rows, year, discipline):
    candidates=candidates_for(rows,year,discipline)
    results=map_items(takeoff_rows,candidates)
    gate=mapping_gate(results)
    return {"results":results,"gate":gate,"year":year,"discipline":discipline}

def require_green(mapping):
    if not mapping["gate"]["green"]:
        raise ValueError("user pricebook mapping gate is not green")
    return mapping
