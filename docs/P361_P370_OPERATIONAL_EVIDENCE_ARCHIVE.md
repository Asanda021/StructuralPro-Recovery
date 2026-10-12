# P361-P370 — Operational Evidence Archive & Retention Integrity

## Scope
This phase adds a deterministic archive boundary around the validated P351-P360
operational-evidence snapshot. The archive is suitable for retaining exact,
integrity-protected evidence records without inventing release evidence.

## Priorities
- P361: versioned archive envelope
- P362: stable archive identity
- P363: nested snapshot integrity validation
- P364: deterministic archive canonicalization
- P365: SHA-256 archive integrity
- P366: fail-closed validation and restore
- P367: stable retention key
- P368: exact archived-snapshot replay
- P369: dedicated regression coverage
- P370: dedicated CI gate

The layer only stores and verifies evidence already produced by the existing
operational-evidence snapshot contract. It does not approve readiness, repair
tampered data, fabricate external provisioning, or replace release controls.

Completion requires dedicated tests, full regression, QA, drawing tests,
Windows smoke/release, PR, merge, Main verification, and post-merge verification.
