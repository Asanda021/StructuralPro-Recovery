"""Static offline preflight for a *single* Windows StructuralPro AI payload.

This command never downloads weights, creates an EXE, launches inference or
grants a license. Human legal review remains a separate acceptance condition.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
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
    # DLLs are shipped and loaded by the binaries too. Every DLL must have
    # independently pinned bytes and verifiable on-disk license provenance.
    deps = data.get("dependencies", [])
    if not isinstance(deps, list):
        blockers.append("invalid_runtime_dependencies")
        deps = []
    declared: set[str] = set()
    for dependency in deps:
        if not isinstance(dependency, dict):
            blockers.append("invalid_runtime_dependency")
            continue
        rel = dependency.get("path")
        if not isinstance(rel, str) or not rel.startswith("ai_runtime/") or not rel.lower().endswith(".dll"):
            blockers.append("invalid_runtime_dependency_path")
            continue
        if rel in declared:
            blockers.append("duplicate_runtime_dependency")
        declared.add(rel)
        hash_expected = dependency.get("sha256")
        evidence = dependency.get("license_evidence")
        evidence_hash = dependency.get("license_evidence_sha256")
        if not all(isinstance(dependency.get(k), str) and dependency[k].strip()
                   for k in ("name", "version", "license_id", "license_evidence", "source_url")):
            blockers.append(f"{rel}:incomplete_dependency_provenance")
        if dependency.get("redistribution_allowed") is not True or dependency.get("legal_review_approved") is not True:
            blockers.append(f"{rel}:redistribution_not_verified")
        try:
            candidate = root / rel
            resolved_root = root.resolve(strict=True)
            candidate.resolve(strict=True).relative_to(resolved_root)
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError("invalid DLL")
            proof = root / str(evidence)
            proof.resolve(strict=True).relative_to(resolved_root)
            if proof.is_symlink() or not proof.is_file():
                raise ValueError("missing license")
            digest = sha256(candidate.read_bytes()).hexdigest()
            license_digest = sha256(proof.read_bytes()).hexdigest()
            if digest != hash_expected or license_digest != evidence_hash:
                blockers.append(f"{rel}:integrity_mismatch")
        except (OSError, ValueError):
            blockers.append(f"{rel}:missing_or_unsafe")
    runtime = root / "ai_runtime"
    observed = set()
    if runtime.is_dir():
        observed = {
            item.relative_to(root).as_posix()
            for item in runtime.rglob("*.dll")
            if item.is_file() or item.is_symlink()
        }
    if observed != declared:
        blockers.append("runtime_dll_inventory_mismatch")
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
