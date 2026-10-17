# Manual-only Windows QA. Never builds, packages, publishes or releases an executable.
[CmdletBinding()]
param([switch]$InstallRequirements)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $root
try {
    if (Test-Path '.github/workflows') {
        $active = @(Get-ChildItem '.github/workflows' -File -ErrorAction SilentlyContinue)
        if ($active.Count -gt 0) {
            throw 'Active GitHub Actions files found: verify release safety before further actions.'
        }
    }
    if ($InstallRequirements) {
        python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    }
    $env:QT_QPA_PLATFORM = 'offscreen'
    python -c "import PySide6; import arabic_reshaper; from bidi.algorithm import get_display; from PySide6.QtWidgets import QApplication; app=QApplication([]); print('QT_RUNTIME_OK')"
    if ($LASTEXITCODE -ne 0) { throw 'Windows Qt or Persian PDF dependencies unavailable.' }
    python -m pytest -q tests/test_finish_takeoff_assemblies.py tests/test_finish_recovery_pr481.py tests/test_assembly_takeoff_persistence.py tests/test_golden_five_storey_building.py tests/test_windows_ui_navigation_dashboard.py
    if ($LASTEXITCODE -ne 0) { throw 'Recovery regression tests failed.' }
    Write-Host 'Targeted Windows tests passed. UI visual / PDF rendering acceptance still requires manual inspection.'
} finally {
    Pop-Location
}
