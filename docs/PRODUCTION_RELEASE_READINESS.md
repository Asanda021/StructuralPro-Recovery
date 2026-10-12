# Production Release Readiness

This is the next bounded delivery stage after the closed P1-P80 engineering roadmap. It does not create P81+ mandatory roadmap phases.

## Completed in repository
- Fail-closed production evidence evaluator.
- Required/optional evidence contract.
- SHA-256 fingerprinting for every present evidence file.
- Deterministic JSON readiness manifest.
- Unit coverage for blocked, partial and fully evidenced states.
- Synthetic fixtures are explicitly excluded from production evidence.

## Required release evidence
1. Customer installer/artifact.
2. Customer entitlement authorization.
3. Real Windows install/run/uninstall evidence.
4. Licensed/provenance-backed pricebook evidence.
5. Exact release-environment dependency/license evidence.

Optional: Windows code signing, bundled GGUF license/checksum, and DWG converter redistribution/runtime terms.

## Release rule
release_ready=true is allowed only when every required item is backed by a non-empty real evidence file. Present evidence is SHA-256 hashed. Missing evidence remains blocked.

Repository tests prove gate behavior; they do not fabricate Windows, commercial, pricebook or third-party evidence.

## Delivery boundary
The next bounded deliverable is the Release Candidate package. No new mandatory roadmap phases are created by this document.

## Evidence hardening completed
- Windows Release now emits a machine-readable third-party license inventory (`StructuralPro-third-party-licenses.csv`) together with the exact pip freeze for the build environment.
- P100 external pricebook synchronization is manual/explicit rather than a Main CI trigger. This keeps external archive availability separate from application CI while preserving fail-closed provenance checks.
- Customer entitlement remains a real authorization boundary: CI cannot manufacture a customer authorization record.
- Customer artifact production remains tied to the Windows installer build, smoke acceptance, SHA-256 manifest and release registry.
