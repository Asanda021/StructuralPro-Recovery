# P171-P180 — BOQ Propagation & Revision Impact

This phase extends P161-P170 from quantity lineage into auditable BOQ lines.

## Implemented
- deterministic BOQ line IDs;
- quantity -> BOQ propagation;
- source identity preservation;
- confidence-based accepted/review/rejected states;
- explicit revision impact for quantity, description, unit, source and status;
- deterministic ordering and fail-closed validation.

## Boundary
No accepted BOQ line is created without source identity and a concrete quantity/unit. No missing engineering quantity is invented.
