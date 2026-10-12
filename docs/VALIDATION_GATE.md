# StructuralPro Validation Gate

Phase 12 establishes an executable validation gate for representative construction projects.

Automated acceptance:
- Golden quantities are checked against the authoritative quantity engine.
- Golden BOQ/estimate finalization is checked through the existing BOQ/estimate engine.
- Real PDF vector, DXF and IFC-format fixtures are parsed and fingerprinted.
- Performance and repeated-load coverage use explicit budgets.
- Security rejects path traversal and secret-like payloads.
- Recovery verifies export/import round-trip integrity.
- Expert validation is explicit and fail-closed.

Evidence rule:
Synthetic/reference fixtures are clearly identified as validation fixtures. They are not represented as customer projects.
Actual customer/project evidence and independent expert sign-off must be supplied before a commercial release gate can claim field validation. The software never fabricates that evidence.

Readiness:
The validation gate is ready only when every required result passes and every required expert case has an approved review.
