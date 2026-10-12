"""Evidence-first multi-discipline coordination boundary for P591-P600."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable

SUPPORTED_DISCIPLINES = frozenset({"structural","architectural","mechanical","electrical","civil","general"})
ALLOWED_RELATIONS = frozenset({"overlap","near","aligned","connected","conflict"})

@dataclass(frozen=True)
class CoordinationRecord:
    record_id: str
    project_id: str
    revision: str
    source_id: str
    discipline: str
    element_id: str
    related_element_id: str
    relation: str
    evidence_ref: str

def _text(*values: str) -> None:
    if any(not isinstance(v,str) or not v.strip() for v in values):
        raise ValueError("required identity/evidence text is missing")

def validate_record(r: CoordinationRecord) -> None:
    _text(r.record_id,r.project_id,r.revision,r.source_id,r.element_id,r.related_element_id,r.evidence_ref)
    if r.discipline not in SUPPORTED_DISCIPLINES: raise ValueError("unsupported discipline")
    if r.relation not in ALLOWED_RELATIONS: raise ValueError("unsupported coordination relation")
    if r.element_id == r.related_element_id: raise ValueError("element cannot coordinate with itself")

def build_coordination_set(records: Iterable[CoordinationRecord]) -> tuple[CoordinationRecord,...]:
    rows=tuple(records); seen=set()
    for r in rows:
        validate_record(r)
        if r.record_id in seen: raise ValueError("duplicate coordination record id")
        seen.add(r.record_id)
    return tuple(sorted(rows,key=lambda r:(r.discipline,r.element_id,r.related_element_id,r.relation,r.record_id)))

def coordination_fingerprint(records: Iterable[CoordinationRecord]) -> str:
    rows=build_coordination_set(records)
    canonical=json.dumps([asdict(r) for r in rows],ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return sha256(canonical.encode("utf-8")).hexdigest()
