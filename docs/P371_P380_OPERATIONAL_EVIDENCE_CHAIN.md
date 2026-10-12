# P371-P380 — Operational Evidence Chain Integrity

## Scope
This phase adds a deterministic chain boundary over the validated P361-P370
operational-evidence archives. It preserves archive order and detects changed,
removed or reordered evidence without fabricating any underlying evidence.

## Priorities
- P371: versioned chain envelope
- P372: deterministic archive sequencing
- P373: nested archive verification
- P374: canonical chain representation
- P375: SHA-256 chain integrity
- P376: fail-closed validation and restore
- P377: order-sensitive replay
- P378: tamper/change detection
- P379: dedicated regression coverage
- P380: dedicated CI gate

Completion requires dedicated tests, full regression, QA, drawing tests,
Windows smoke/release, PR, merge, Main verification, and post-merge verification.
