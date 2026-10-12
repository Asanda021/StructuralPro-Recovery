"""P85 — code/unit-first bridge to the pricing engine."""
from dataclasses import dataclass
from core.estimate.user_pricebook_code_mapping_v1 import index_code_unit

@dataclass(frozen=True)
class PriceRowsResult:
    accepted: tuple
    missing_rate: int

@dataclass(frozen=True)
class PricingBridgeResult:
    accepted: tuple
    unresolved: tuple
    year: int
    discipline: str

def to_price_rows(normalized_rows):
    """Return only rows with a usable unit price; fail closed only at the caller."""
    accepted = tuple(row for row in normalized_rows if row.unit_price is not None)
    return PriceRowsResult(
        accepted=accepted,
        missing_rate=sum(row.unit_price is None for row in normalized_rows),
    )

def map_and_price(takeoff_rows, normalized_rows, year, discipline):
    index=index_code_unit(normalized_rows,year,discipline)
    accepted=[]; unresolved=[]
    for item in takeoff_rows:
        key=(str(item.get("item_code","")).strip(),str(item.get("unit","")).strip())
        row=index.get(key)
        if row is None:
            unresolved.append(str(item.get("takeoff_id","")))
            continue
        accepted.append({"takeoff_id":str(item["takeoff_id"]),"item_code":row.item_code,
                         "unit":row.unit,"quantity":item["quantity"],
                         "unit_price":row.rate,"total":item["quantity"]*row.rate})
    if unresolved:
        raise ValueError("pricebook bridge unresolved items")
    return PricingBridgeResult(tuple(accepted),tuple(unresolved),year,discipline)
