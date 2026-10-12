# StructuralPro Final Release Integrity

## Traceability chain

A release candidate must be traceable through this chain:

VERSION -> source commit -> Windows runner -> packaged VERSION -> StructuralPro.exe -> versioned installer -> SHA-256 -> release manifest

The Windows release workflow records source commit, workflow run metadata, packaged version, and SHA-256/size for release artifacts in StructuralPro-ReleaseManifest.json and StructuralPro-SHA256SUMS.txt.

## Version boundary

VERSION is the canonical application version.

The Inno Setup template contains the stable placeholder __VERSION__. The Windows workflow replaces that exact placeholder with the canonical VERSION. It does not depend on a hard-coded historical version string.

The build script rejects an explicitly supplied version that differs from VERSION, and verifies the VERSION embedded in the PyInstaller payload.

## Installer boundary

The installer is built only after the payload exists and the payload VERSION has been validated.

The generated installer must be named StructuralPro-<VERSION>-Setup.exe.

The installer is configured for a per-user installation under LocalAppData with PrivilegesRequired=lowest, avoiding an implicit requirement for administrative privileges.

## Artifact integrity

The checksum file covers StructuralPro.exe, packaged VERSION, and the versioned installer.

The manifest repeats SHA-256 and file-size evidence and links those artifacts to the source commit and GitHub Actions run metadata.

## Code-signing boundary

Code signing is deliberately outside the application source tree's private-key boundary.

A future signed release may add a Windows signing step using a securely provisioned certificate/signing service. No private signing material belongs in the repository, PyInstaller payload, installer template, or release manifest.

An unsigned build must not be described as code-signed.

## Release evidence

A release is not considered Windows-verified merely because the YAML is syntactically valid. The actual Windows Actions run must complete successfully and its artifacts must be inspected before release publication.