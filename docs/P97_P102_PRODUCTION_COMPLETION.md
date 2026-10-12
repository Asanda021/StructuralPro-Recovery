# P97–P102 Production Completion

## Scope
P97–P102 hardens pricebook extraction, archive provenance, official artifact identity,
the 1399–1404 artifact matrix, scaled code/unit pricing, and the full-building rule
registry.

## Fail-closed guarantees
- Ambiguous Excel headers are rejected.
- Multiple worksheets are inspected.
- Archive members are audited individually; parse errors are not silently discarded.
- Official artifacts must be non-empty, non-HTML and hash-addressable.
- Every pricebook matrix cell requires provenance.
- Code/unit conflicts fail closed.
- Quantity rules require explicit source/version/code/unit/formula provenance.
- No coefficients or prices are fabricated by this block.
