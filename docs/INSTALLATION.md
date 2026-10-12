# StructuralPro Installation Guide

## Windows

The supported release path is the Windows package produced by the repository's packaging workflow.

### Installer contents

The Inno Setup template is:
- packaging/installer.iss

The application package is built from:
- packaging/build_windows.ps1
- packaging/structuralpro.spec

The canonical version is:
- VERSION

The release workflow verifies that the packaged VERSION matches the canonical VERSION before producing the installer.

### Installation steps

1. Obtain an installer from an approved StructuralPro release.
2. Verify the release version and, where provided, its checksum/signature.
3. Run the installer.
4. Follow the installation prompts.
5. Start StructuralPro from the installed application or Start Menu shortcut.
6. Create/open a test project and confirm local save, takeoff and report behavior before migrating production projects.

### Optional local AI model

A GGUF model may be installed or bundled only when its license permits the intended redistribution/commercial use. Model checksum and compatibility should be validated before activation.

### DWG support

Native DWG parsing is not assumed to be provided by the Python application itself. The supported architecture uses an explicit local converter boundary where a tested converter is available. Do not silently upload drawings to an unapproved cloud service.

## Upgrade

Before upgrading:
1. Finish or checkpoint active work.
2. Create a project backup.
3. Export critical reports if required.
4. Install the new version.
5. Open the project.
6. Run integrity validation.
7. Check key quantities, estimates and financial totals.

Never overwrite the only copy of a project with an unverified migration.

## Uninstall

Use the Windows uninstaller. Preserve project data and backups separately when they are stored outside the application installation directory.
