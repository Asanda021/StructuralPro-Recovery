"""Priority 43 — release artifact integrity contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_release_workflow_validates_manifest_artifact_hashes():
    source = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "Validate release artifact hashes" in source
    assert "Get-FileHash -Algorithm SHA256" in source
    assert "manifest.artifacts" in source

def test_release_manifest_contains_artifact_integrity_fields():
    source = (ROOT / "packaging/generate_release_manifest.ps1").read_text(encoding="utf-8")
    assert 'schema="structuralpro.release-manifest.v1"' in source
    assert "sha256=(Get-FileHash -Algorithm SHA256" in source
    assert "size_bytes=(Get-Item $file).Length" in source
