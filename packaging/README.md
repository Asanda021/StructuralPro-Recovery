# One final Windows edition

StructuralPro ships as **one comprehensive Windows product**, identified by
`EDITION=unified`. Light/Standard/Pro/Enterprise markers remain compatibility
readers for old data/tests; they are not separate new deliverables. The unified
profile enables the full feature set and cannot be downgraded by an environment
edition marker.

The reviewed entry point is `packaging/build_windows_edition.ps1`, which accepts
only `unified`, verifies canonical VERSION and prevalidated local assets, and
requires explicit owner approval before creating executables or an installer.
`-ValidateOnly` checks staged assets without building. The base Windows build
script cannot create an installer directly. Do not bypass this path with a raw
PyInstaller command. No EXE, installer or release was authorized or produced by
the phase-6 closeout mission.

The intended final outputs, after separate approval and phase-8 verification,
are a single StructuralPro Windows payload and its installer, not edition-specific
products. Packaging readiness is separate from having a built, signed and tested
binary.

Local GGUF use is noncommercial per the owner. Commercial AI licensing is not a
phase-6 gate. Actual model identity, SHA, runtime and applicable use/redistribution
terms must still be verified before weights are used or included. Placeholder
manifests are not an installed working model. The tested offline rule-based
fallback remains available when model assets are absent. Existing release asset
checks are not removed by this policy decision.
