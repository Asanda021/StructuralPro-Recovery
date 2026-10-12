# P36 — Product Packaging

P36 establishes the first explicit commercial edition contract for StructuralPro.

## Scope

StructuralPro is packaged as a comprehensive construction takeoff, BOQ and
estimating platform for building works, not as a concrete-only product.

The editions are:

- Light — core takeoff/BOQ, drawing/PDF workflow, reports and offline core.
- Standard — adds CAD/BIM, revision, estimating and local AI.
- Pro — adds AI takeoff, collaboration and API integration.
- Enterprise — the complete capability set plus enterprise controls.

This phase defines capability boundaries only. It does not invent prices,
licenses, third-party datasets, model weights or cloud dependencies.

## Implementation contract

core/platform/product.py is the single source of truth for edition-to-feature
mapping. The matrix is monotonic (Light ⊆ Standard ⊆ Pro ⊆ Enterprise), unknown
editions fail closed, and a license cannot request capabilities outside its
selected edition.

## Acceptance

- Four named editions exist.
- The matrix covers the cross-domain takeoff product.
- Feature boundaries are deterministic and offline.
- License-feature validation is fail-closed.
- Dedicated P36 tests pass alongside the existing regression suite.

## Next phase

P37 is the production deployment/release execution layer; it consumes this
edition contract rather than redefining commercial capability boundaries.
