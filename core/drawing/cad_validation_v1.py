"""P57 — evidence-first DWG/DXF validation contracts."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

CadKind = Literal["dwg", "dxf"]

@dataclass(frozen=True)
class CadEvidence:
    source_id: str
    kind: CadKind
    layer: str
    entity_type: str
    geometry_count: int
    block_name: str
    text: str
    dimension_value: float | None
    observed_at: str

@dataclass(frozen=True)
class CadValidation:
    source_id: str
    entity_count: int
    layers: tuple[str, ...]
    blocks: tuple[str, ...]
    dimensions: tuple[float, ...]
    text_count: int
    geometry_count: int
    fingerprint: str

def validate_evidence(rows: tuple[CadEvidence, ...]) -> None:
    if not rows:
        raise ValueError("CAD validation requires explicit extracted evidence")
    for row in rows:
        if not all((row.source_id.strip(), row.kind, row.layer.strip(), row.entity_type.strip(), row.observed_at.strip())):
            raise ValueError("incomplete CAD evidence")
        if row.geometry_count < 0:
            raise ValueError("geometry_count cannot be negative")
        if row.dimension_value is not None and row.dimension_value < 0:
            raise ValueError("dimension value cannot be negative")

def validate_cad(rows: tuple[CadEvidence, ...]) -> CadValidation:
    validate_evidence(rows)
    source_ids={r.source_id for r in rows}
    if len(source_ids) != 1:
        raise ValueError("one CAD source per validation")
    source_id=next(iter(source_ids))
    layers=tuple(sorted({r.layer for r in rows}))
    blocks=tuple(sorted({r.block_name for r in rows if r.block_name.strip()}))
    dimensions=tuple(sorted(r.dimension_value for r in rows if r.dimension_value is not None))
    material="|".join(f"{r.source_id}:{r.kind}:{r.layer}:{r.entity_type}:{r.geometry_count}:{r.block_name}:{r.text}:{r.dimension_value}:{r.observed_at}" for r in sorted(rows,key=lambda x:(x.layer,x.entity_type,x.block_name,x.text)))
    return CadValidation(source_id,len(rows),layers,blocks,dimensions,sum(bool(r.text.strip()) for r in rows),sum(r.geometry_count for r in rows),sha256(material.encode()).hexdigest())
