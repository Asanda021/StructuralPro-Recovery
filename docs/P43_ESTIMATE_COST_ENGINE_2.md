# P43 — Estimate & Cost Engine 2.0

## Scope
A domain-neutral estimating layer for the complete building/civil platform.

## Included
- Accepted quantity → estimate line conversion.
- Explicit material, labor, machinery and other cost categories.
- Exact item/category/unit rate matching.
- Source, version and provenance on every rate.
- Transparent category cost breakdown.
- Explicit grand total.
- Multiple pricing/quantity scenarios without automatic selection.
- Deterministic estimate fingerprint.

## Fail-closed rules
Missing rates, duplicate identities, invalid numbers, unit/category mismatches and mixed currencies are rejected.

No hidden currency conversion, escalation, tax, contingency, rounding policy, productivity factor or invented rate is applied.

## Acceptance
Implementation → dedicated tests → CI → Merge → post-merge main verification.
