# ERVIRA ↔ StructuralPro Product Source of Truth

StructuralPro is the canonical software source for its own product identity, capability status, version and release metadata.

## Authority

- Repository: `Asanda021/StructuralPro`
- Contract: `contracts/product-contract.json`
- Version: `VERSION`
- Release evidence: GitHub release/tag artifacts
- ERVIRA consumes this contract and must not redefine the same facts independently.

## Status vocabulary

- `available`: implemented and validated.
- `integration`: an integration boundary exists, but the capability is not a fully released standalone customer feature.
- `planned`: not released.

## Release rule

No ERVIRA download or customer-facing "available" claim is valid without a real StructuralPro release artifact and verification evidence.

## Sync rule

ERVIRA CI must fetch the canonical contract and validate its derived mirror. Any mismatch in product ID, version, capability IDs/status, edition status or release/download metadata fails the gate.
