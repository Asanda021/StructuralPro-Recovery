# P37 — Real Product Deployment

## Purpose
P37 turns the verified StructuralPro product into a real, distributable production release.

The current production surface is **Windows desktop**, because the repository identifies Windows as the canonical first production client. Android/Telegram remain shared-contract clients rather than being falsely marked as production deployments.

## Production path
1. A release tag (`vX.Y.Z`) is created.
2. The workflow verifies that the tag exactly matches `VERSION`.
3. A clean Windows payload is built from the canonical source.
4. The installer is generated from the existing Inno Setup template.
5. The installer is installed and launched in an end-to-end smoke test.
6. SHA-256 checksums and a release manifest are generated and verified.
7. The validated payload is uploaded as workflow artifacts.
8. A GitHub Release is published with the installer, executable, checksums, manifest and dependency inventory.

## Fail-closed rules
A release is blocked when:
- `VERSION` is invalid;
- the tag does not match `VERSION`;
- the packaged version differs from `VERSION`;
- the executable or installer is missing;
- installer installation fails;
- the installed application smoke test fails;
- an artifact hash or size does not match the generated manifest.

## Deployment boundary
This phase provides **real production distribution**, not a fake cloud-hosted deployment. StructuralPro remains offline-first and Windows-desktop-first. No external hosted service, database, API key, or cloud runtime is invented as a substitute for the product's actual architecture.

The resulting GitHub Release is the canonical public production distribution channel until a separate hosted service is deliberately specified and verified.

## Rollback
Rollback is release-based: users can return to a previously validated GitHub Release artifact. A failed tag never becomes a published release because publication occurs only after all build, installer, smoke and integrity gates pass.
