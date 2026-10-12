from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_windows_release_script_uses_canonical_version():
    text=(ROOT/"packaging/build_windows.ps1").read_text()
    assert "Get-Content VERSION" in text
    assert "StructuralPro.exe" in text

def test_installer_paths_are_valid_in_template():
    text=(ROOT/"packaging/installer.iss").read_text()
    assert 'Source: "..\\dist\\StructuralPro\\*"' in text
    assert "OutputBaseFilename=StructuralPro-{#MyAppVersion}-Setup" in text
    assert '#define MyAppVersion "__VERSION__"' in text

def test_release_workflow_validates_payload_and_installer():
    text=(ROOT/".github/workflows/windows-release.yml").read_text()
    assert "dist/StructuralPro/StructuralPro.exe" in text
    assert "dist/StructuralPro/VERSION" in text
    assert "StructuralPro-*-Setup.exe" in text
