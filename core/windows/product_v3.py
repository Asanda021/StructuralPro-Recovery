"""P65 — hardened Windows release/workspace contract."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re

@dataclass(frozen=True)
class WindowsRelease:
    version: str
    installer: str
    executable: str
    sha256: str
    architecture: str
    channel: str
    min_windows: str

@dataclass(frozen=True)
class WindowsWorkspace:
    project_extension: str
    backup_extension: str
    autosave_interval_seconds: int
    recovery_enabled: bool
    offline_enabled: bool

def validate_release(r: WindowsRelease) -> None:
    if not all((r.version, r.installer, r.executable, r.sha256, r.architecture, r.channel, r.min_windows)):
        raise ValueError("incomplete Windows release")
    if r.architecture not in {"x64", "arm64"} or r.channel not in {"stable", "beta"}:
        raise ValueError("unsupported Windows release")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", r.sha256):
        raise ValueError("invalid SHA-256")
    if not r.installer.lower().endswith((".exe", ".msi")) or not r.executable.lower().endswith(".exe"):
        raise ValueError("invalid Windows artifact")

def validate_workspace(w: WindowsWorkspace) -> None:
    if not w.project_extension.startswith(".") or not w.backup_extension.startswith("."):
        raise ValueError("invalid workspace extensions")
    if w.project_extension == w.backup_extension:
        raise ValueError("project and backup extensions must differ")
    if w.autosave_interval_seconds < 5:
        raise ValueError("unsafe autosave interval")
    if not w.recovery_enabled or not w.offline_enabled:
        raise ValueError("recovery/offline must be enabled")

def release_manifest(r: WindowsRelease, w: WindowsWorkspace) -> dict:
    validate_release(r)
    validate_workspace(w)
    return {
        "platform": "windows",
        "architecture": r.architecture,
        "version": r.version,
        "installer": r.installer,
        "executable": r.executable,
        "sha256": r.sha256.lower(),
        "channel": r.channel,
        "min_windows": r.min_windows,
        "workspace": {
            "project_extension": w.project_extension,
            "backup_extension": w.backup_extension,
            "autosave_interval_seconds": w.autosave_interval_seconds,
            "recovery_enabled": w.recovery_enabled,
            "offline_enabled": w.offline_enabled,
        },
        "install": {"clean_install": True, "upgrade": True, "rollback": True, "uninstall": True},
    }

def manifest_fingerprint(manifest: dict) -> str:
    return sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
