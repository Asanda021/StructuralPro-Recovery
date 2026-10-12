# StructuralPro — production status

This document records the repository state after the production hardening priorities. It distinguishes repository-verified capabilities from release-time external provisioning.

## Repository-verified and CI-tested

- Windows desktop packaging builds reproducibly.
- The generated Inno Setup installer is validated for payload, version and file integrity.
- Priority 49 performs a real Windows installer E2E smoke: install → verify executable/version → launch installed application → uninstall.
- Core quantity/takeoff, BOQ, pricing, persistence, recovery, reports/export, drawing, AI-boundary, performance and regression surfaces have executable tests.
- Main CI runs the test, QA and Windows smoke surfaces after merges.

## Release-time external evidence still required

These are not silently fabricated by the repository and must be supplied/verified before a commercial release:

- Licensed/verified official Iranian annual price-list datasets.
- A redistributable GGUF model, with license and checksum evidence, if bundled.
- An approved DWG converter/SDK, with vendor redistribution/runtime terms, if DWG conversion is shipped.
- Windows code-signing certificate and secure signing procedure, if signed distribution is required.
- Exact third-party dependency/license evidence for the release environment.

## Product-scope limitations

The repository deliberately does not claim capabilities that are outside the current deterministic implementation boundary, including native DWG parsing without an external converter and full computer-vision plan recognition.

Android and Telegram are contract-based client surfaces; polished native distribution remains a separate packaging/distribution deliverable.

## Release interpretation

A green repository CI result means the defined executable repository scope is passing. It does not by itself prove that external commercial assets, licenses, certificates or vendor-installed converters have been provisioned.

The product remains offline-first: core local project, takeoff, calculation and reporting paths do not require a cloud service.
