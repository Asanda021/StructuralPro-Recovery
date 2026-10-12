# StructuralPro Release Checklist

## Version
- [ ] VERSION contains a valid MAJOR.MINOR.PATCH value.
- [ ] Release notes identify the same version.
- [ ] Tag is exactly v<version>.

## Source quality
- [ ] Focused tests pass.
- [ ] Full regression tests pass.
- [ ] Python compile gate passes.
- [ ] Production-gate tests pass.
- [ ] No known blocking defects remain undocumented.

## Packaging
- [ ] packaging/build_windows.ps1 validates VERSION.
- [ ] PyInstaller produces StructuralPro.exe.
- [ ] Packaged VERSION is present and matches the canonical VERSION.
- [ ] Inno Setup installer builds.
- [ ] Installer filename contains the version.
- [ ] Installer paths are validated.
- [ ] Installer is tested on a clean supported Windows environment when available.

## Licensing and dependencies
- [ ] License architecture does not embed a signing secret.
- [ ] Production public-key verification path is configured when commercial licensing is enabled.
- [ ] Commercial license expiration behavior is tested.
- [ ] Commercial license revocation policy is defined and tested.
- [ ] Feature entitlement identifiers are defined without duplicates.
- [ ] Third-party dependencies have compatible redistribution terms.
- [ ] Any bundled GGUF model has verified license and checksum.
- [ ] Any bundled/required DWG converter has verified redistribution/installation terms.
- [ ] Official price-list data is sourced and licensed/verified.

## Commercial security
- [ ] Commercial security gates are satisfied.
- [ ] No private signing key or credential is embedded in source/package.
- [ ] Third-party dependency/model/converter/catalog licensing evidence is recorded.
- [ ] Code-signing policy and certificate provisioning are defined when required.
- [ ] Third-party compliance inventory and exact dependency inventory are reviewed.
- [ ] Release artifact SHA-256 checksums are generated and retained.

## Documentation
- [ ] User Guide is current.
- [ ] Installation Guide is current.
- [ ] Developer Guide is current.
- [ ] Configuration documentation is current.
- [ ] License documentation is current.
- [ ] Commercial license lifecycle documentation is current.
- [ ] Backup/Restore documentation is current.
- [ ] Troubleshooting documentation is current.
- [ ] Version/release process is current.

## Release evidence
- [ ] Release commit is identified.
- [ ] CI results are recorded.
- [ ] Windows runner build status is actually observed, not inferred.
- [ ] Installer artifact is retained.
- [ ] Checksums/signatures are generated where applicable.
- [ ] Release notes are published.
- [ ] Main branch is re-checked after merge.

## Known limitation

A repository-level green test result does not by itself prove that external proprietary datasets, third-party converters, model licenses, code-signing certificates or Windows hardware acceptance have been provisioned.
