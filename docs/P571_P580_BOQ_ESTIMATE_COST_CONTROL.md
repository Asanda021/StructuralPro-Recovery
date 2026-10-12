# P571-P580 — BOQ → Estimate → Cost Control

## Scope
This phase establishes a deterministic evidence-first commercial chain:

**accepted BOQ quantity → explicit price → estimate → explicit committed/actual cost → remaining cost**

## Rules
- Quantities must already be accepted by an upstream quantity/evidence layer.
- Every BOQ line carries source and revision identity.
- Every rate carries source, version and provenance.
- Pricing requires an exact item-code and unit match.
- Currency is explicit; mixed currencies fail closed.
- Arithmetic is visible and deterministic.
- Actual costs are caller-supplied entries with provenance.
- No hidden currency conversion, escalation, contingency, tax, rounding policy, or invented quantity/rate is applied.
- A negative remaining value is retained as a transparent overrun signal; it is not silently clamped to zero.

## Acceptance gates
1. Unit/currency compatibility.
2. Duplicate identity rejection.
3. Missing-price fail-closed behavior.
4. Deterministic estimate fingerprint.
5. Explicit cost-control arithmetic.
6. Dedicated tests and CI.

## Verification
The phase is validated against the current `main` baseline before merge.
