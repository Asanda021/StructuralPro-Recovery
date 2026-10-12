# StructuralPro implementation status

## Current verified state

StructuralPro is a Windows-first offline construction quantity, estimation and project platform with executable CI coverage across core application, drawing, persistence, calculation/quantity, UI, reporting/export and release surfaces.

The current Main branch has completed Priority 49, including real Windows installer acceptance testing. The production evidence boundary is fail-closed and is now wired to produce a machine-readable third-party license inventory with the Windows release artifact.

## Verified release surfaces

- Desktop PySide6 application structure
- Project/takeoff/estimate/report modules
- Pricing and commercial modules
- CAD/DXF/DWG adapter architecture
- IFC/BIM adapter architecture
- Offline mode and synchronization queue architecture
- Local AI facade and deterministic fallback
- Reproducible Windows packaging
- Installer install/run/uninstall smoke acceptance
- Regression, QA, drawing and Windows smoke workflows

## Release evidence boundary

The first four production blockers are handled as follows:

- **Customer artifact:** the Windows Release workflow builds, smoke-tests, hashes and publishes the Windows installer/payload artifact on Main/tag release executions.
- **Entitlement authorization:** release/download authorization remains explicitly entitlement-gated; no customer entitlement is fabricated by CI.
- **Pricebook provenance:** P100 is an explicit/manual external-data import. It records source URL, archive page, SHA-256 and row coverage and no longer runs automatically on every Main push, so external archive outages cannot poison product CI. Archive-sourced data is not mislabeled as official.
- **Third-party licenses:** the Windows Release artifact now includes `StructuralPro-third-party-licenses.csv` alongside `pip-freeze`, giving the exact build environment a machine-readable license inventory.

## Remaining release dependencies

The repository now includes a fail-closed Production Release Readiness evaluator and evidence manifest. The following still require real external provisioning/evidence rather than speculative repository implementation:

- Licensed/verified official Iranian annual price-list datasets.
- A redistributable GGUF model and license/checksum evidence if a model is bundled.
- An approved DWG converter/SDK and redistribution/runtime terms if DWG conversion is shipped.
- Windows code-signing certificate and secure signing procedure where required.
- Final third-party dependency/license evidence for the exact release environment.
- Android and Telegram native distribution deliverables, if those clients are included in the release scope.

These dependencies are intentionally explicit so repository tests do not create a false claim of commercial readiness.

## Release evidence closure hardening

- Windows Release now fails closed if the generated third-party license inventory is empty or contains an `UNKNOWN`/blank license entry.
- The repository-side release evidence boundary is documented in `docs/PRODUCTION_RELEASE_EVIDENCE_CLOSURE.md`.
- External legal/customer facts are deliberately not fabricated: entitlement, redistribution rights for pricebooks/DWG SDKs, and any required signing certificate must come from the real rights holder/release account.
