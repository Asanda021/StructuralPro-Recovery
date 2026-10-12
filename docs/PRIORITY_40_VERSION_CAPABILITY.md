# Priority 40 — Cross-Platform Version & Capability Contract

The repository uses VERSION as the canonical application version.

## Changes
- Android versionName is derived from the repository VERSION file instead of a duplicated literal.
- Optional drawing backends remain explicit and are not promoted to mandatory core dependencies.
- DXF/DWG and IFC parsing keep actionable runtime messages when their optional local backends are not installed.
- Tests protect the version and capability contract from drift.

## Scope
This is an internal quality/stability improvement. It does not publish a release, add cloud dependencies, or change engineering calculation authority.


Verification note: regression contract corrected to the current Kotlin DSL spacing (`minSdk = 29`).
