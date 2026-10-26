"""Static offline preflight for a *single* Windows StructuralPro AI payload.

This command never downloads weights, creates an EXE, launches inference or
grants a license. Human legal review remains a separate acceptance condition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from core.ai.release_gate import inspect_ai_release_assets

_EXPECTED_EXECUTABLES = {
    "runtime_text": "ai_runtime/llama-cli.exe",
    "runtime_vision": "ai_runtime/llama-mtmd-cli.exe",
}


def validate_staged_unified_payload(root: str | Path) -> tuple[str, ...]:
    root = Path(root)
    manifest = root / "AI_RELEASE_MANIFEST.json"
    inspected = inspect_ai_release_assets(manifest, root)
    blockers = list(inspected.blockers)
    if not manifest.is_file() or manifest.is_symlink():
        return tuple(sorted(set(blockers + ["missing_AI_RELEASE_MANIFEST"])))
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return tuple(sorted(set(blockers + [f"invalid_AI_RELEASE_MANIFEST:{type(exc).__name__}"])))
    if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
        return tuple(sorted(set(blockers + ["invalid_assets"])))
    assets = {
        asset.get("kind"): asset
        for asset in data["assets"]
        if isinstance(asset, dict) and isinstance(asset.get("kind"), str)
    }
    for kind, expected in _EXPECTED_EXECUTABLES.items():
        if assets.get(kind, {}).get("path") != expected:
            blockers.append(f"{kind}:incorrect_windows_executable")
    for kind in ("model", "mmproj"):
        item = assets.get(kind, {})
        name = item.get("path")
        if not isinstance(name, str) or not name.startswith("models/") or not name.endswith(".gguf"):
            blockers.append(f"{kind}:invalid_model_package_path")
    edition = root / "EDITION"
    if edition.exists():
        if edition.is_symlink() or edition.read_text(encoding="utf-8").strip().lower() != "unified":
            blockers.append("legacy_or_unsafe_EDITION_marker")
    # Do not allow unlicensed DLL dependencies to enter a signed distribution.
    # They must have their own separately reviewed manifest/license evidence
    # before this preflight can be considered a release readiness certificate.
    if (root / "ai_runtime").is_dir():
        for dll in (root / "ai_runtime").glob("*.dll"):
            if dll.is_symlink() or dll.is_file():
                blockers.append("dll_dependency_not_explicitly_reviewed")
                break
    return tuple(sorted(set(blockers)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-root", type=Path, required=True)
    args = parser.parse_args(argv)
    blockers = validate_staged_unified_payload(args.asset_root)
    print(json.dumps({
        "release_preflight": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "claim": "byte-integrity and declared permissions only; actual copyright grant requires external legal approval",
    }, sort_keys=True))
    return 0 if not blockers else 2


if __name__ == "__main__":
    sys.exit(main())
