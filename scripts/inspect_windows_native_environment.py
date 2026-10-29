"""Read-only allowlisted Windows Python, Qt, native-library environment inventory.

Outputs package versions and digests of known relevant DLL/PYD files only.
Never writes filesystem paths, process command lines, identities, env vars,
raw Windows logs, memory dumps or broad dependency inventories.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys

PKGS = (
    "PySide6", "PySide6-Addons", "PySide6-Essentials", "shiboken6",
    "pytest", "ifcopenshell", "psutil", "pypdf", "PyMuPDF",
    "openpyxl", "reportlab", "python-docx", "ezdxf",
)
LIB_NAMES = {
    "qt6core.dll", "qt6gui.dll", "qt6widgets.dll", "qt6network.dll",
    "qwindows.dll", "pyside6.abi3.dll", "shiboken6.abi3.dll",
    "qtcore.pyd", "qtgui.pyd", "qtwidgets.pyd", "_sqlite3.pyd",
    "sqlite3.dll", "python312.dll", "vcruntime140.dll",
    "vcruntime140_1.dll", "msvcp140.dll",
}


def fingerprint() -> dict:
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import QCoreApplication, qVersion
    from PySide6.QtWidgets import QApplication
    import psutil

    app = QApplication.instance() or QApplication([])
    packages = {}
    for name in PKGS:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None

    dlls = {}
    # Inspect loaded native modules of the separate *probe* process.
    # Only permitted module names and SHA-256 digests, never full paths.
    for m in psutil.Process().memory_maps(grouped=False):
        src = Path(m.path)
        key = src.name.lower()
        if key not in LIB_NAMES or key in dlls:
            continue
        try:
            dlls[key] = {
                "file_name": src.name,
                "sha256": hashlib.file_digest(src.open("rb"), "sha256").hexdigest(),
                "size_bytes": src.stat().st_size,
            }
        except (OSError, PermissionError):
            dlls[key] = {"file_name": src.name, "status": "hash_unavailable"}

    # qwindows.dll is typically loaded with Qt's windows platform plugin.
    from PySide6.QtCore import QLibraryInfo
    manifest = {
        "kind": "windows_native_qt_dependency_fingerprint_v1",
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_arch": platform.architecture()[0],
        "windows_version": platform.version(),
        "windows_release": platform.release(),
        "platform": sys.platform,
        "sqlite_version": sqlite3.sqlite_version,
        "sqlite_module_version": sqlite3.version,
        "pyside_version": pyside_version,
        "qt_runtime_version": qVersion(),
        "qt_library_paths_count": len(QCoreApplication.libraryPaths()),
        "qt_plugins_path_exists": bool(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)),
        "packages": packages,
        "loaded_allowlist_native_modules": dlls,
        "raw_environment_variables_included": False,
        "full_paths_or_secrets_included": False,
        "memory_dumps_included": False,
    }
    assert app is not None
    return manifest


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") != "windows":
        parser.error("This is a native-Windows Qt-only evidence probe")
    manifest = fingerprint()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "python": manifest["python"], "windows_version": manifest["windows_version"],
        "pyside": manifest["pyside_version"], "qt": manifest["qt_runtime_version"],
        "sqlite": manifest["sqlite_version"],
        "dlls_detected": sorted(manifest["loaded_allowlist_native_modules"]),
    }, ensure_ascii=False))
if __name__ == "__main__":
    main()
