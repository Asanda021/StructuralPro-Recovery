"""Priority 49 — Windows installer acceptance contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_release_runs_installed_application_smoke():
    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "windows_installer_smoke.ps1" in workflow
    assert "STRUCTURALPRO_SMOKE" not in workflow.split("Run installed application acceptance smoke", 1)[0]


def test_installer_smoke_validates_payload_and_version():
    script = (ROOT / "packaging/windows_installer_smoke.ps1").read_text(encoding="utf-8")
    assert "/VERYSILENT" in script
    assert "StructuralPro.exe" in script
    assert "VERSION" in script
    assert "Installed application smoke exited with code" in script
