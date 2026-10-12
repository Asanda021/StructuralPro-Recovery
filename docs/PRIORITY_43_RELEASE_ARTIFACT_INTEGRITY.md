# Priority 43 — Release Artifact Integrity

## Goal
Make the internal Windows release pipeline verify that the generated release manifest actually matches the produced artifacts.

## Implementation
After the manifest is generated, the Windows release workflow recomputes SHA-256 for every artifact recorded in `manifest.artifacts` and compares both hash and file size.

This is an internal packaging-integrity check only; it does not publish a release.

## Acceptance
- Missing artifacts fail the workflow.
- Hash mismatches fail the workflow.
- Size mismatches fail the workflow.
- Existing Windows packaging and release checks remain green.
