# P581-P590 — Revision Intelligence + Change Impact

## Scope
A deterministic, evidence-first comparison boundary for project revisions.

**Revision A → Element Change → Quantity Change → BOQ Change → Estimate Impact → Cost Impact**

The phase compares explicit caller-supplied snapshots. It does not read geometry,
invent quantities, infer prices, or silently reconcile differences.

## Contract
Each snapshot requires:
- project identity
- revision identity
- source identity
- element identity
- explicit quantity
- explicit BOQ quantity
- explicit estimate amount
- explicit actual cost

The engine classifies each element as:
- added
- removed
- modified

For every change it exposes explicit deltas for quantity, BOQ quantity,
estimate and actual cost.

## Fail-closed rules
- Missing identity/provenance is rejected.
- Non-finite or negative supplied numeric values are rejected.
- A snapshot belonging to another revision is rejected.
- Duplicate record or element identities are rejected.
- Cross-project comparison is rejected.
- Old and new revisions must differ.
- No price, geometry, engineering property, or quantity is inferred.

## Verification gates
1. Added/removed/modified classification.
2. Explicit quantity/BOQ/estimate/cost deltas.
3. No-change detection.
4. Revision and project identity checks.
5. Duplicate identity rejection.
6. Deterministic fingerprint.
7. Dedicated CI tests.
8. Post-merge verification against main.
