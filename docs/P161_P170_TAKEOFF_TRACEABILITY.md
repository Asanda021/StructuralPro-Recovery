# P161-P170 — Takeoff Traceability & Revision Impact

Production layer after P151-P160 Drawing Production.

## Implemented
- deterministic quantity evidence records;
- source -> element -> quantity -> BOQ lineage;
- confidence-based accept/review/reject;
- fail-closed missing-source and missing-quantity handling;
- duplicate-safe trace links;
- deterministic revision-impact comparison.

## Boundaries
- no quantity is invented;
- no accepted quantity without source identity;
- low-confidence results are review-only;
- BOQ links are created only from accepted quantity evidence;
- revision impact is explicit and field-level.

## Traceability
Drawing source -> recognized element -> quantity evidence -> BOQ

Revision A -> Revision B -> changed quantity/source/status -> explicit impact

The layer consumes P141-P160/P151-P160 provenance; it does not weaken those boundaries.
