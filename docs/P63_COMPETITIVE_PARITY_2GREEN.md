# P63 — Competitive Parity 2-Green

P63 upgrades the remaining competitive gaps from contract-only readiness toward executable product evidence.

## Covered gaps

1. Official/historical Iranian price-book ingestion: CSV and XLSX import, normalized rows, year coverage and deterministic fingerprints.
2. Takeoff-to-price-book mapping: exact evidence-first mapping plus conservative similarity mapping with review gates.
3. Iranian real-project validation: reference-vs-system quantity comparison with relative-error metrics; no fabricated project evidence.
4. Cloud collaboration: revision-aware event application, idempotent/stale handling and explicit base-fingerprint conflicts.
5. Product UX: required edit/back/menu/restart/review/calculate actions, RTL, staged input and review gate.
6. Green-2 readiness: deterministic thresholds are executable in tests; production claims remain evidence-bound.

## Important boundary

The repository does not invent official Iranian price-book rows, real customer projects, cloud infrastructure, or measured market accuracy. Users can import official source files and real project references; the engine validates them deterministically.

## Acceptance

A capability may be reported as Green-2 only when its required evidence gate passes. This keeps competitive reporting honest while making the implementation executable.
