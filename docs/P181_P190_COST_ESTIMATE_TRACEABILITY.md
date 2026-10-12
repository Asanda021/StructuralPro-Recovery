# P181-P190 — Cost & Estimate Traceability

## Purpose
Extend the auditable chain from BOQ into pricing and estimate without inventing prices.

## Scope
- Preserve BOQ identity into estimate lines.
- Attach explicit price evidence and source identity.
- Apply confidence gates: accepted/review/rejected.
- Calculate deterministic estimate amount as quantity × unit price.
- Detect revision impact for quantity, unit price, currency, source, status, and removal.
- Keep estimate identity stable when quantity changes.

## Guardrails
- Missing source evidence cannot produce an accepted line.
- Missing price evidence produces no estimate line.
- Low confidence is routed to review.
- No market price is inferred or invented.
- All outputs are deterministic and auditable.

## Traceability
Drawing/BIM → Element → Quantity → BOQ → Price → Estimate

Revision propagation:
Revision → Quantity Impact → BOQ Impact → Estimate Impact

## Verification
Dedicated tests cover traceability, confidence gating, source rejection, quantity/price revision impact, stable identity, and BOQ lineage preservation.
