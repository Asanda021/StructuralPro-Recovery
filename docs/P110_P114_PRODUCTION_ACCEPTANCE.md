# P110-P114 Production Acceptance

## Scope

This block closes the first estimate workflow segment of the roadmap:

- **P110 — Revision Intelligence:** deterministic revision deltas for quantity, rebar, BOQ and dimensions, with provenance and human-review flags.
- **P111 — Quantity → Estimate:** explicit takeoff/BOQ-to-cost bridge with validation and auditable factors.
- **P112 — Assembly / Cost Build-up:** reusable assemblies expand a base quantity into deterministic material/labour components.
- **P113 — Estimate Workspace:** estimate snapshots can be compared without mutation and expose line-level and total cost deltas.
- **P114 — BOQ / Scenarios:** production quantity scenarios cover representative members and preserve concrete, rebar, 12 m stock-bar and cut/waste outputs.

## Evidence rules

1. No geometry, price or quantity is inferred by the acceptance layer.
2. Unresolved pricing and cross-source duplicates remain reviewable/fail-closed in the underlying estimating engine.
3. Revision changes are deterministic and carry source/revision identity.
4. Assembly expansion is deterministic from the declared base quantity.
5. The production gate requires the dedicated acceptance test and regression suite to pass.

## Completion criterion

P110-P114 is considered complete only after:

**Implementation → PR → CI green → regression green → merge → main verification.**
