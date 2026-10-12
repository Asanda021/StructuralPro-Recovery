# P42 — Revision Intelligence 2.0

## Scope
Domain-neutral revision intelligence for the complete building/civil takeoff platform.

## Included
- Revision-to-revision element comparison.
- Added / removed / modified classification.
- Member-type and description changes.
- Dimension changes with explicit before/after values.
- Quantity and count deltas.
- Rebar/steel/material quantity deltas when supplied by evidence.
- BOQ quantity impact.
- Source/provenance identity on every compared element.
- Deterministic fingerprint and summary.
- Review-required flag for every material change.

## Safety
The engine compares caller-supplied evidence only. It never reconstructs missing geometry, invents quantities, silently reconciles conflicts, or auto-approves a revision.

## Acceptance
Implementation → dedicated tests → CI → Merge → post-merge main verification.
