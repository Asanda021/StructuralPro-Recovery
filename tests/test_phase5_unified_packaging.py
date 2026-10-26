"""Offline-only Windows unified packaging preflight fixtures; never build an EXE."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import importlib.util

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "packaging" / "verify_unified_payload.py"
SPEC = importlib.util.spec_from_file_location("structuralpro_unified_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_staged_unified_payload = MODULE.validate_staged_unified_payload


def staged_unified_assets(tmp_path: Path) -> tuple[Path, dict]:
    entries = (
        ("model", "models/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"),
        ("mmproj", "models/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf"),
        ("runtime_text", "ai_runtime/llama-cli.exe"),
        ("runtime_vision", "ai_runtime/llama-mtmd-cli.exe"),
    )
    assets = []
    for kind, rel in entries:
        file = tmp_path / rel
        file.parent.mkdir(exist_ok=True)
        data = ("synthetic-non-GGUF-" + kind).encode()
        file.write_bytes(data)
        license_rel = "licenses/" + kind + ".txt"
        license_file = tmp_path / license_rel
        license_file.parent.mkdir(exist_ok=True)
        proof = ("SYNTHETIC FIXTURE ONLY " + kind).encode()
        license_file.write_bytes(proof)
        assets.append({
            "kind": kind, "name": kind, "version": "fixture",
            "path": rel, "sha256": sha256(data).hexdigest(),
            "source_url": "https://example.invalid/no-download", "license_id": "TEST_ONLY",
            "license_evidence": license_rel,
            "license_evidence_sha256": sha256(proof).hexdigest(),
            "architecture": "x86_64", "commercial_use_allowed": True,
            "redistribution_allowed": True, "legal_review_approved": True,
        })
    manifest = {
        "schema_version": 1, "product": "StructuralPro", "edition": "unified",
        "offline_required": True, "external_api_required": False,
        "owner_release_approval": True, "assets": assets, "dependencies": [],
    }
    (tmp_path / "AI_RELEASE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "EDITION").write_text("unified\n", encoding="utf-8")
    return tmp_path, manifest


def test_unified_offline_preflight_accepts_byte_valid_synthetic_contract(tmp_path):
    source, _ = staged_unified_assets(tmp_path)
    assert validate_staged_unified_payload(source) == ()
    # Fixture approval is NOT evidence that any real model is commercially licensed.
    assert not (source / "StructuralPro.exe").exists()


def test_unified_preflight_rejects_legacy_and_missing_approvals(tmp_path):
    source, manifest = staged_unified_assets(tmp_path)
    (source / "EDITION").write_text("enterprise")
    assert "legacy_or_unsafe_EDITION_marker" in validate_staged_unified_payload(source)
    (source / "EDITION").write_text("unified")
    manifest["owner_release_approval"] = False
    (source / "AI_RELEASE_MANIFEST.json").write_text(json.dumps(manifest))
    assert "missing_owner_release_approval" in validate_staged_unified_payload(source)


def test_unified_preflight_rejects_wrong_exe_and_injected_dll(tmp_path):
    source, manifest = staged_unified_assets(tmp_path)
    manifest["assets"][2]["path"] = "ai_runtime/unapproved.exe"
    (source / "AI_RELEASE_MANIFEST.json").write_text(json.dumps(manifest))
    assert "runtime_text:incorrect_windows_executable" in validate_staged_unified_payload(source)
    manifest["assets"][2]["path"] = "ai_runtime/llama-cli.exe"
    (source / "AI_RELEASE_MANIFEST.json").write_text(json.dumps(manifest))
    injected = source / "ai_runtime" / "side-loaded.dll"
    injected.write_bytes(b"not licensed")
    assert "runtime_dll_inventory_mismatch" in validate_staged_unified_payload(source)


def test_unified_preflight_accepts_exact_hashed_reviewed_dll_contract(tmp_path):
    source, manifest = staged_unified_assets(tmp_path)
    dll = source / "ai_runtime" / "ggml.dll"
    dll.write_bytes(b"synthetic dll")
    proof = source / "licenses" / "ggml.txt"
    proof.write_bytes(b"synthetic MIT fixture, not legal opinion")
    manifest["dependencies"] = [{
        "path": "ai_runtime/ggml.dll", "name": "ggml", "version": "fixture",
        "source_url": "https://example.invalid/no-download",
        "license_id": "TEST_ONLY", "license_evidence": "licenses/ggml.txt",
        "sha256": sha256(dll.read_bytes()).hexdigest(),
        "license_evidence_sha256": sha256(proof.read_bytes()).hexdigest(),
        "redistribution_allowed": True, "legal_review_approved": True,
    }]
    (source / "AI_RELEASE_MANIFEST.json").write_text(json.dumps(manifest))
    assert validate_staged_unified_payload(source) == ()
    dll.write_bytes(b"tampered")
    assert any("integrity_mismatch" in x for x in validate_staged_unified_payload(source))


@pytest.mark.skipif(sys.platform != "win32", reason="native PowerShell required")
def test_windows_single_edition_validate_only_does_not_build(tmp_path):
    root, _ = staged_unified_assets(tmp_path / "source")
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    assert pwsh, "real Windows runner must have PowerShell"
    version = (REPO_ROOT / "VERSION").read_text().strip()
    script = REPO_ROOT / "packaging" / "build_windows_edition.ps1"
    cmd = [pwsh, "-NoProfile", "-NonInteractive", "-File", str(script),
           "-Version", version, "-Edition", "unified",
           "-AssetSource", str(root), "-ValidateOnly"]
    result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no binary or installer built" in result.stdout
    assert not (root / "StructuralPro.exe").exists()
    # Invalid legacy product edition never reaches build even in ValidateOnly.
    invalid = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-File", str(script),
         "-Version", version, "-Edition", "pro",
         "-AssetSource", str(root), "-ValidateOnly"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=45,
    )
    assert invalid.returncode != 0
