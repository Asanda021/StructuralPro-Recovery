from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def test_installer_uses_stable_version_placeholder():
    text = read("packaging/installer.iss")
    assert '#define MyAppVersion "__VERSION__"' in text
    assert "0.1.0" not in text

def test_build_script_rejects_version_drift():
    text = read("packaging/build_windows.ps1")
    assert "$canonicalVersion=(Get-Content VERSION -Raw).Trim()" in text
    assert "$Version -ne $canonicalVersion" in text
    assert "Packaged VERSION" in text

def test_release_workflow_has_stable_placeholder_injection():
    text = read(".github/workflows/windows-release.yml")
    assert "installer.generated.iss" in text
    assert "__VERSION__" in text
    assert '#define MyAppVersion "0.1.0"' not in text

def test_release_workflow_enforces_tag_version_consistency():
    text = read(".github/workflows/windows-release.yml")
    assert 'if ("${{ github.ref_type }}" -eq "tag" -and "v$v" -ne "${{ github.ref_name }}"' in text

def test_release_workflow_generates_traceability_manifest():
    text = read(".github/workflows/windows-release.yml")
    assert "generate_release_manifest.ps1" in text
    assert "StructuralPro-ReleaseManifest.json" in text
    assert "source_commit" in read("packaging/generate_release_manifest.ps1")

def test_release_manifest_script_contains_source_to_artifact_chain():
    text = read("packaging/generate_release_manifest.ps1")
    for marker in ("source_commit", "workflow_run_id", "version", "packaged_version", "sha256"):
        assert marker in text

def test_checksum_script_requires_all_release_artifacts():
    text = read("packaging/generate_sha256.ps1")
    assert "StructuralPro.exe" in text
    assert "StructuralPro-$version-Setup.exe" in text
    assert "if (-not (Test-Path $installerPath))" in text