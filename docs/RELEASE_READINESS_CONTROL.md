# Release Readiness Control

This is a bounded product-control feature, not a new mandatory roadmap phase.

It centralizes the final customer-release gate already used across StructuralPro and ERVIRA. The control is deliberately fail-closed: repository implementation cannot turn missing real-world evidence into a release claim.

## Required evidence

1. Real customer installer/artifact exists.
2. Customer entitlement authorization is verified.
3. Real Windows installation/run/uninstall evidence exists.
4. Pricebook provenance/licensing evidence is verified.
5. Exact release-environment third-party dependency/license evidence exists.

## Optional evidence

- Windows code-signing certificate and signing evidence.
- Redistributable GGUF model license/checksum evidence.
- Approved DWG converter/runtime redistribution terms.

Optional evidence improves release quality but never unlocks a release by itself.

## Current policy

The repository remains release_ready=false until all required evidence is actually present. This is intentional and prevents synthetic CI/contracts from being presented as customer-live evidence.

The same control can be consumed by ERVIRA release/download authorization without coupling StructuralBot data to StructuralPro.