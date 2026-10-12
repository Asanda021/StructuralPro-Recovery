"""P102 — source-bound full-building quantity rule registry.

This registry deliberately contains no invented coefficients. A rule is executable
only when its source/version/code/unit identity is explicit.
"""
from __future__ import annotations
from dataclasses import dataclass

DISCIPLINES=(
 "architecture","structure","earthwork","concrete","masonry","waterproofing",
 "roofing","doors_windows","finishes","painting","flooring","ceiling",
 "electrical","mechanical","plumbing","fire_protection","external_works",
)

@dataclass(frozen=True)
class QuantityRule:
    rule_id:str
    discipline:str
    source:str
    version:str
    item_code:str
    unit:str
    formula:str

def validate_rule(r):
    if r.discipline not in DISCIPLINES: raise ValueError("unsupported building discipline")
    if not all(isinstance(x,str) and x.strip() for x in
               (r.rule_id,r.source,r.version,r.item_code,r.unit,r.formula)):
        raise ValueError("quantity rule provenance is incomplete")

def validate_registry(rules,required_disciplines=DISCIPLINES):
    rows=tuple(rules)
    if not rows: raise ValueError("quantity rule registry is empty")
    for r in rows: validate_rule(r)
    present={r.discipline for r in rows}
    missing=sorted(set(required_disciplines)-present)
    duplicate_ids=len({r.rule_id for r in rows})!=len(rows)
    if duplicate_ids: raise ValueError("duplicate quantity rule id")
    return {"rows":len(rows),"disciplines":tuple(sorted(present)),
            "missing_disciplines":tuple(missing),"complete":not missing}
