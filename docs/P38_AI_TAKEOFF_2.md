# P38 — AI Takeoff 2.0

## Scope
P38 upgrades the existing P23–P27 AI takeoff chain without replacing it.

- deterministic component detection, including rebar terminology
- explicit-unit dimension extraction
- reuse of existing proposal, normalization, production and review gates
- confidence remains visible and review-gated
- reviewer feedback is captured with source provenance and a deterministic fingerprint
- no missing geometry or quantity is invented

## Boundary
P38 is an evidence-first proposal layer. It does not silently approve AI results and
does not turn inferred dimensions into engineering/design decisions.

## Acceptance
The dedicated P38 test suite covers component recognition, explicit dimensions,
review-only production packages, feedback provenance and fail-closed validation.
