"""P62 — complete-building takeoff coverage and scope contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

DISCIPLINES = (
    "architecture","structure","earthwork","concrete","masonry","waterproofing",
    "roofing","doors_windows","finishes","painting","flooring","ceiling",
    "electrical","mechanical","plumbing","fire_protection","external_works",
)

@dataclass(frozen=True)
class TakeoffScope:
    discipline: str
    item_code: str
    description: str
    unit: str
    quantity: float
    source_id: str

def validate_scope(rows: Iterable[TakeoffScope]) -> tuple[TakeoffScope,...]:
    out=[]; seen=set()
    for row in rows:
        if row.discipline not in DISCIPLINES: raise ValueError("unsupported building discipline")
        if any(not isinstance(v,str) or not v.strip() for v in (row.item_code,row.description,row.unit,row.source_id)):
            raise ValueError("takeoff row identity is incomplete")
        if row.quantity < 0: raise ValueError("quantity cannot be negative")
        key=(row.discipline,row.item_code)
        if key in seen: raise ValueError("duplicate takeoff scope item")
        seen.add(key); out.append(row)
    return tuple(out)

def coverage_report(rows: Iterable[TakeoffScope], required: Iterable[str]=DISCIPLINES) -> dict[str,object]:
    normalized=validate_scope(rows)
    required_set=set(required)
    unknown=required_set-set(DISCIPLINES)
    if unknown: raise ValueError("unknown required discipline")
    present={r.discipline for r in normalized}
    missing=tuple(sorted(required_set-present))
    return {
        "complete": not missing,
        "required_disciplines": tuple(sorted(required_set)),
        "covered_disciplines": tuple(sorted(present)),
        "missing_disciplines": missing,
        "row_count": len(normalized),
    }
