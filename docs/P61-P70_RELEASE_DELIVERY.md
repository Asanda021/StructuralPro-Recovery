# P61-P70 — Release / Delivery

P61-P70 is the StructuralPro-to-ERVIRA release delivery block.

Implemented gates:
- P61 Release Registry
- P62 Version Synchronization
- P63 Build Synchronization
- P64 Release Notes Synchronization
- P65 Artifact Registry
- P66 SHA-256 Verification
- P67 Download Authorization boundary
- P68 Windows Installer Delivery
- P69 Installation Detection
- P70 Installed-Version + License E2E Verification boundary

The Windows release workflow builds the application and installer on a real Windows runner, installs the generated installer, launches the installed application in smoke mode, generates SHA-256 evidence, validates the release manifest, and generates a machine-readable release registry.

Customer release remains fail-closed: CI evidence does not grant entitlement and public pages must not expose an unrestricted customer artifact URL.

P61-P70 is complete only after both the PR workflow and the post-merge Main workflow are green.
