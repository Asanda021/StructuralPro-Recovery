"""Execute the build script with failed native tools and stale payload files."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell runtime unavailable")
@pytest.mark.parametrize("failed_step", range(1, 6))
def test_native_failure_stops_build_before_stale_payload_is_accepted(tmp_path, failed_step):
    packaging = tmp_path / "packaging"
    packaging.mkdir()
    shutil.copyfile(ROOT / "packaging/build_windows.ps1", packaging / "build_windows.ps1")
    (tmp_path / "VERSION").write_text("1.2.3", encoding="ascii")
    payload = tmp_path / "dist/StructuralPro"
    bridge = payload / "dwg-bridge"
    bridge.mkdir(parents=True)
    (payload / "StructuralPro.exe").write_bytes(b"stale executable")
    (payload / "VERSION").write_text("1.2.3", encoding="ascii")
    (bridge / "StructuralPro.DwgBridge.exe").write_bytes(b"stale bridge")
    runner = tmp_path / "run.ps1"
    runner.write_text("""
param([int]$FailAt)
$global:Step = 0
function Invoke-FakeNative {
    $global:Step += 1
    if ($global:Step -eq $FailAt) { $global:LASTEXITCODE = 91 }
    else { $global:LASTEXITCODE = 0 }
}
function python { Invoke-FakeNative }
function dotnet { Invoke-FakeNative }
try {
    & "$PSScriptRoot/packaging/build_windows.ps1"
    Write-Output "BUILD_WRONGLY_SUCCEEDED"
    exit 2
} catch {
    Write-Output "STOPPED_AT=$global:Step"
    Write-Output $_.Exception.Message
    exit 91
}
""", encoding="utf-8")
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(runner), "-FailAt", str(failed_step)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 91, result.stdout + result.stderr
    assert f"STOPPED_AT={failed_step}" in result.stdout
    assert "failed with exit code 91" in result.stdout
    assert "BUILD_WRONGLY_SUCCEEDED" not in result.stdout
    assert not (tmp_path / "dist/StructuralPro-1.2.3-SHA256.txt").exists()
