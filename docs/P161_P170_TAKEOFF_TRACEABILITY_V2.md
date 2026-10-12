# P161-P170 — Takeoff Traceability V2

This phase hardens the chain from recognized drawing evidence to accepted takeoff.

## Ten gates
- P161 explicit candidate normalization
- P162 fail-closed missing quantity
- P163 confidence/review gate
- P164 invalid-value rejection
- P165 source coverage
- P166 orphan-source review
- P167 unresolved-candidate reporting
- P168 deterministic ordering
- P169 candidate fingerprinting
- P170 source identity acceptance boundary

The layer does not estimate missing dimensions, invent quantities, infer units, or
promote unsupported candidates. Accepted quantities require an element identity,
explicit quantity, unit, source lineage, and sufficient confidence.

Chain:
**drawing source → engineering element → normalized candidate → quantity evidence → BOQ**
