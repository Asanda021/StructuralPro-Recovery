# P1091-P1120 — Final Product Acceptance

This phase defines the final, deterministic acceptance boundary before release-candidate work.

## Required acceptance areas
The gate requires exactly these seven checks:
- core functionality
- domain outputs
- UI surfaces
- data integrity
- release artifacts
- production boundary
- release health

Every check must be present and strictly boolean. Unknown or missing checks fail closed, and any false check blocks acceptance.

## Evidence
The gate produces a canonical SHA-256 fingerprint so the same evidence produces the same identity regardless of mapping insertion order. It performs no network or deployment operations.

## Completion rule
P1091-P1120 is green only after implementation, focused tests, dedicated CI, PR merge, and successful post-merge Main verification.
