# P351-P360 — Operational Evidence Snapshot & Replay Integrity

## Scope
This phase adds a deterministic, integrity-protected snapshot boundary for the
already validated P341-P350 operational-evidence result.

## Priorities
- P351: versioned snapshot schema
- P352: deterministic canonicalization
- P353: SHA-256 snapshot integrity
- P354: required-field/type validation
- P355: unsupported-schema rejection
- P356: deterministic JSON serialization
- P357: integrity-checked restoration
- P358: exact replay comparison
- P359: dedicated regression coverage
- P360: dedicated CI gate

This layer consumes existing evidence only. It does not fabricate, repair,
download, sign, approve, or bypass readiness/runtime/diagnostics/audit evidence.
Tampered or malformed snapshots fail closed.

Completion requires dedicated tests, full regression, QA, drawing tests,
Windows smoke/release, PR, merge, Main verification, and post-merge verification.
