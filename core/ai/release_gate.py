"""A1 offline distribution gate for one StructuralPro Windows product.

This verifies *bytes* and the completeness of publisher-supplied licensing
evidence, not the legal authenticity of an external copyright holder's grant.
No network, model download, subprocess, UI access or project mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

REQUIRED_KINDS = frozenset(("model", "mmproj", "runtime"))


@dataclass(frozen=True)
class AIReleaseCheck:
    ready: bool
    blockers: tuple[str, ...]
    sha256_by_kind: dict[str, str]


def inspect_ai_release_assets(manifest_path: str | Path, asset_root: str | Path) -> AIReleaseCheck:
    """Require all 3 assets, independent license evidence and publisher approval.

    A synthetic test fixture may satisfy this data contract; that is NOT a
    review of actual licenses. Real distributions require owner/legal review.
    """
    blockers: list[str] = []
    digests: dict[str, str] = {}
    root = Path(asset_root)
    source = Path(manifest_path)
    if not root.is_dir() or root.is_symlink() or not source.is_file() or source.is_symlink():
        return AIReleaseCheck(False, ("invalid_or_missing_manifest_root",), {})
    try:
        if source.stat().st_size > 131072:
            raise ValueError("oversized_manifest")
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return AIReleaseCheck(False, (f"invalid_manifest:{type(exc).__name__}",), {})
    if not isinstance(manifest, dict):
        return AIReleaseCheck(False, ("invalid_manifest_shape",), {})
    if manifest.get("schema_version") != 1 or manifest.get("product") != "StructuralPro":
        blockers.append("wrong_product_or_schema")
    if manifest.get("edition") != "unified":
        blockers.append("tiered_edition_not_allowed")
    if manifest.get("offline_required") is not True or manifest.get("external_api_required") is not False:
        blockers.append("offline_privacy_not_declared")
    if manifest.get("owner_release_approval") is not True:
        blockers.append("missing_owner_release_approval")
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        return AIReleaseCheck(False, tuple(blockers+["invalid_assets"]), {})
    kinds = [x.get("kind") if isinstance(x, dict) else None for x in assets]
    if len(assets) != 3 or set(kinds) != REQUIRED_KINDS or len(set(kinds)) != 3:
        blockers.append("missing_or_duplicate_model_projector_runtime")
    for asset in assets:
        if not isinstance(asset, dict):
            blockers.append("invalid_asset")
            continue
        kind = str(asset.get("kind", ""))
        file_name = asset.get("path")
        digest = asset.get("sha256")
        if kind not in REQUIRED_KINDS:
            blockers.append("unknown_asset_kind")
            continue
        if not isinstance(file_name, str) or not file_name or Path(file_name).is_absolute() or "\\" in file_name:
            blockers.append(f"{kind}:invalid_path")
            continue
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            blockers.append(f"{kind}:invalid_sha256")
            continue
        if not all(isinstance(asset.get(k), str) and asset[k].strip()
                   for k in ("name", "version", "source_url", "license_id", "license_evidence", "architecture")):
            blockers.append(f"{kind}:incomplete_provenance")
        if asset.get("commercial_use_allowed") is not True or asset.get("redistribution_allowed") is not True:
            blockers.append(f"{kind}:unverified_commercial_rights")
        if asset.get("legal_review_approved") is not True:
            blockers.append(f"{kind}:missing_legal_review")
        license_digest = asset.get("license_evidence_sha256")
        license_path = asset.get("license_evidence")
        if not isinstance(license_digest, str) or len(license_digest) != 64 or any(
            x not in "0123456789abcdef" for x in license_digest.lower()
        ):
            blockers.append(f"{kind}:missing_license_evidence_sha256")
        else:
            try:
                if not isinstance(license_path, str) or not license_path:
                    raise ValueError("missing license evidence path")
                proof = root.joinpath(license_path)
                if proof.is_symlink() or not proof.is_file():
                    raise ValueError("unsafe evidence")
                proof.resolve(strict=True).relative_to(root.resolve(strict=True))
                observed = sha256(proof.read_bytes()).hexdigest()
                if observed != license_digest.lower():
                    blockers.append(f"{kind}:license_evidence_hash_mismatch")
            except (OSError, ValueError):
                blockers.append(f"{kind}:license_evidence_missing_or_unsafe")
        try:
            path = root.joinpath(file_name)
            # All parent directories must be real, not a symlink escape.
            root_real = root.resolve(strict=True)
            path_real = path.resolve(strict=True)
            path_real.relative_to(root_real)
            current = path
            while current != root:
                if current.is_symlink():
                    raise ValueError("symlink component")
                current = current.parent
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError("nonregular asset")
            value = sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    value.update(block)
            actual = value.hexdigest()
            digests[kind] = actual
            if actual != digest.lower():
                blockers.append(f"{kind}:sha256_mismatch")
        except (OSError, ValueError):
            blockers.append(f"{kind}:unsafe_or_missing")
    return AIReleaseCheck(not blockers, tuple(sorted(set(blockers))), digests)
